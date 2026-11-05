"""Module discovery and checking of a program by the generated type checker"""

import pathlib

from . import syntax
from .generated import Finite_Map, Option, Programs, Reasons
from .generated.exit_codes import Exit
from .messages import message
from .syntax import (
    ModuleBody,
    Name,
    Program,
    QualifiedName,
    Reason,
    parse_name,
    qualified_name,
)

MAIN = parse_name("__main__")


def module_path(q: Name, base_dir: pathlib.Path) -> pathlib.Path:
    stem = pathlib.Path(*q)
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    assert (base_dir / stem).is_dir()
    return base_dir / stem


def module_name(base_dir: pathlib.Path, path: pathlib.Path) -> Name | None:
    rel = path.relative_to(base_dir)
    parts = rel.parent.parts if rel.name == "__init__.py" else rel.with_suffix("").parts
    return parts if len(parts) > 0 else None


def proper_prefixes(q: Name) -> list[Name]:
    return [q[:i] for i in range(1, len(q))]


def module_names(base_dir: pathlib.Path) -> set[Name]:
    names = {
        module_name(base_dir, p) for p in base_dir.rglob("*.py") if "__pycache__" not in p.parts
    }
    return {p for q in names if q is not None for p in [q, *proper_prefixes(q)]}


# Module and reason of an ill-formed program
type IllFormed = tuple[QualifiedName, Reason]
type OurLangRejects = IllFormed | syntax.ParserRejects


def parse_program(entry_path: pathlib.Path) -> Program:
    """Entry module parsed first, so its errors take precedence"""
    base_dir = entry_path.parent
    names = sorted(module_names(base_dir), key=str)
    return program(
        {
            MAIN: parse_module(MAIN, entry_path),
            **{q: parse_module(q, module_path(q, base_dir)) for q in names},
        }
    )


def parse_module(q: Name, path: pathlib.Path) -> ModuleBody:
    """A package directory is an empty module"""
    try:
        return syntax.parse_module("" if path.is_dir() else path.read_text(), str(path), q)
    except syntax.ParserRejects as e:
        e.module = q
        raise


def program(bodies: dict[Name, ModuleBody]) -> Program:
    return Finite_Map.fmap_of_list([(qualified_name(q), body) for q, body in bodies.items()])


def check(M: Program) -> IllFormed | None:
    match Programs.check_program(M):
        case Option.None_():
            return None
        case Option.Some((q, r)):
            return (q, r)
        case result:
            raise AssertionError(f"unexpected result: {result}")


def check_program(entry_path: pathlib.Path) -> OurLangRejects | None:
    try:
        return check(parse_program(entry_path))
    except syntax.ParserRejects as e:
        return e


def check_module(path: pathlib.Path) -> OurLangRejects | None:
    """Check the module at path as a program of one module"""
    try:
        return check(program({MAIN: parse_module(MAIN, path)}))
    except syntax.ParserRejects as e:
        return e


def exit_code(rejection: OurLangRejects | None) -> Exit:
    match rejection:
        case None:
            return Exit.OK
        case syntax.ParserRejects():
            return Exit.NOT_ALLOWED
        case _:
            return Exit.ILL_FORMED


def error_path(rejection: OurLangRejects, entry_path: pathlib.Path) -> pathlib.Path:
    """File of the module at fault"""
    match rejection:
        case syntax.ParserRejects():
            q = rejection.module
        case ((x, xs), _):
            q = (x, *xs)
    return entry_path if q is None or q == MAIN else module_path(q, entry_path.parent)


def format_rejection(rejection: OurLangRejects | None, filename: str) -> str:
    match rejection:
        case None:
            return f"{filename}: ok"
        case syntax.ParserRejects() if rejection.line is not None:
            return f"{filename}:{rejection.line}:{rejection.col}: {rejection.msg}"
        case syntax.ParserRejects():
            return f"{filename}: {rejection.msg}"
        case (_, Reasons.Located((line, col), r)):
            return f"{filename}:{line}:{col}: {message(r)}"
        case (_, r):
            return f"{filename}: {message(r)}"


def format_program_rejection(rejection: OurLangRejects | None, entry_path: pathlib.Path) -> str:
    path = entry_path if rejection is None else error_path(rejection, entry_path)
    return format_rejection(rejection, str(path))
