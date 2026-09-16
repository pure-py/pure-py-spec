import ast
import pathlib
import sys
from collections.abc import Iterator, Mapping

import syntax
from check_module import check_module
from contexts import MAIN, PREDEFINED_MODULES
from reasons import IllFormed, IllFormedModule, IllFormedProgram
from type_syntax import QualifiedName, proper_prefixes


def module_path(q: QualifiedName, base_dir: pathlib.Path) -> pathlib.Path | None:
    stem = pathlib.Path(*q.parts)
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    return base_dir / stem if (base_dir / stem).is_dir() else None


def parse(path: pathlib.Path) -> ast.Module:
    if path.is_dir():
        return ast.Module(body=[], type_ignores=[])
    source = path.read_text()
    try:
        m = syntax.parse(source, str(path))
    except SyntaxError as e:
        raise IllFormedProgram(f"{path}: parse error: {e}") from e
    unsupported = syntax.check_syntax_module(m)
    if unsupported is not None:
        unsupported.msg = f"{path}: {unsupported.msg}"
        raise unsupported
    return m


def module_name(base_dir: pathlib.Path, path: pathlib.Path) -> QualifiedName | None:
    rel = path.relative_to(base_dir)
    parts = rel.parent.parts if rel.name == "__init__.py" else rel.with_suffix("").parts
    return QualifiedName(parts) if len(parts) > 0 else None


def module_names(base_dir: pathlib.Path) -> set[QualifiedName]:
    names = {
        module_name(base_dir, p)
        for p in base_dir.rglob("*.py")
        if "__pycache__" not in p.parts
    }
    return {p for q in names if q is not None for p in [q, *proper_prefixes(q)]}


class Program(Mapping[QualifiedName, ast.Module]):
    """The program: every module under the entry's directory by name, with the
    predefined modules, each body parsed when the module is first loaded, so a
    module that is never imported is not checked."""

    def __init__(self, entry_path: pathlib.Path) -> None:
        self.base_dir = entry_path.parent
        self.paths: dict[QualifiedName, pathlib.Path] = {MAIN: entry_path}
        self.parsed: dict[QualifiedName, ast.Module] = {
            q: ast.Module(body=[], type_ignores=[]) for q in PREDEFINED_MODULES
        }
        self.names = set(self.parsed) | set(self.paths) | module_names(self.base_dir)

    def path(self, q: QualifiedName) -> pathlib.Path:
        if q not in self.paths:
            found = module_path(q, self.base_dir)
            assert found is not None
            self.paths[q] = found
        return self.paths[q]

    def __getitem__(self, q: QualifiedName) -> ast.Module:
        if q not in self.names:
            raise KeyError(q)
        if q not in self.parsed:
            self.parsed[q] = parse(self.path(q))
        return self.parsed[q]

    def __iter__(self) -> Iterator[QualifiedName]:
        return iter(self.names)

    def __len__(self) -> int:
        return len(self.names)


def check_program(entry_path: pathlib.Path) -> IllFormed | syntax.Unsupported | None:
    program = Program(entry_path)
    try:
        check_module(program[MAIN], program, MAIN, {})
        return None
    except IllFormedModule as e:
        e.msg = f"{program.path(e.module or MAIN)}: {e.msg}"
        return e
    except (IllFormed, syntax.Unsupported) as e:
        return e


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: check_program.py <entry-file>")
        sys.exit(1)
    entry = pathlib.Path(sys.argv[1])
    result = check_program(entry)
    if result is None:
        print(f"{entry}: ok")
        sys.exit(0)
    print(result.msg)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
