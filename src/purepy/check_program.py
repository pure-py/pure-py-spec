import ast
import pathlib

from . import syntax
from .check_module import check_module, format_result
from .classes import PREDEFINED_CLASSES
from .contexts import MAIN, PREDEFINED_MODULES
from .reasons import IllFormed, IllFormedModule
from .type_syntax import Name, proper_prefixes


def module_path(q: Name, base_dir: pathlib.Path) -> pathlib.Path:
    stem = pathlib.Path(*q.parts)
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    assert (base_dir / stem).is_dir()
    return base_dir / stem


def parse(path: pathlib.Path) -> ast.Module:
    if path.is_dir():
        return ast.Module(body=[], type_ignores=[])
    source = path.read_text()
    try:
        m = syntax.parse(source, str(path))
    except SyntaxError as e:
        raise syntax.ParseError(e) from e
    unsupported = syntax.check_syntax_module(m)
    if unsupported is not None:
        raise unsupported
    return m


def module_name(base_dir: pathlib.Path, path: pathlib.Path) -> Name | None:
    rel = path.relative_to(base_dir)
    parts = rel.parent.parts if rel.name == "__init__.py" else rel.with_suffix("").parts
    return Name(parts) if len(parts) > 0 else None


def module_names(base_dir: pathlib.Path) -> set[Name]:
    names = {
        module_name(base_dir, p) for p in base_dir.rglob("*.py") if "__pycache__" not in p.parts
    }
    return {p for q in names if q is not None for p in [q, *proper_prefixes(q)]}


def parse_program(entry_path: pathlib.Path) -> dict[Name, ast.Module]:
    """Modules by name, every module of the source tree parsed, the main module first"""
    base_dir = entry_path.parent
    names = sorted(module_names(base_dir), key=str)
    return {
        **{q: ast.Module(body=[], type_ignores=[]) for q in PREDEFINED_MODULES},
        MAIN: parse_module(MAIN, entry_path),
        **{q: parse_module(q, module_path(q, base_dir)) for q in names},
    }


def parse_module(q: Name, path: pathlib.Path) -> ast.Module:
    try:
        return parse(path)
    except syntax.Unsupported as e:
        e.module = q
        raise


def check_program(entry_path: pathlib.Path) -> IllFormed | syntax.Unsupported | None:
    try:
        M = parse_program(entry_path)
        check_module(M[MAIN], M, MAIN, PREDEFINED_CLASSES)
        return None
    except (IllFormed, syntax.Unsupported) as e:
        return e


# File of the module at fault, or of the entry module for a program-level error
def error_path(result: IllFormed | syntax.Unsupported, entry_path: pathlib.Path) -> pathlib.Path:
    q = result.module if isinstance(result, (IllFormedModule, syntax.Unsupported)) else None
    return entry_path if q is None or q == MAIN else module_path(q, entry_path.parent)


def format_program_result(
    result: IllFormed | syntax.Unsupported | None, entry_path: pathlib.Path
) -> str:
    path = entry_path if result is None else error_path(result, entry_path)
    return format_result(result, str(path))
