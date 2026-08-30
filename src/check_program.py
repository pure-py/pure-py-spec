import ast
import pathlib
import sys
from collections.abc import Iterator, Mapping

import syntax
from check_module import check_module, proper_prefixes
from contexts import PREDEFINED_MODULES
from reasons import IllFormed, IllFormedModule, IllFormedProgram


def is_module(name: str, base_dir: pathlib.Path) -> pathlib.Path | None:
    stem = name.replace(".", "/")
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    return base_dir / stem if (base_dir / stem).is_dir() else None


def parse(path: pathlib.Path) -> ast.Module:
    if path.is_dir():
        return ast.Module(body=[], type_ignores=[])
    source = path.read_text()
    try:
        tree = syntax.parse(source, str(path))
    except SyntaxError as e:
        raise IllFormedProgram(f"{path}: parse error: {e}") from e
    unsupported = syntax.supported_module(tree)
    if unsupported is not None:
        unsupported.msg = f"{path}: {unsupported.msg}"
        raise unsupported
    return tree


def module_name(base_dir: pathlib.Path, path: pathlib.Path) -> tuple[str, ...]:
    rel = path.relative_to(base_dir)
    return rel.parent.parts if rel.name == "__init__.py" else rel.with_suffix("").parts


def source_tree(base_dir: pathlib.Path) -> set[str]:
    """Names of the modules under `base_dir`, the entry file among them under
    its own name, and of the packages they imply."""
    parts = (
        module_name(base_dir, p)
        for p in base_dir.rglob("*.py")
        if "__pycache__" not in p.parts
    )
    names = {".".join(p) for p in parts if p}
    return {n for name in names for n in {name, *proper_prefixes(name)}}


class Program(Mapping[str, ast.Module]):
    """The program: every module under the entry's directory by name, with the
    predefined modules, each body parsed when the module is first loaded, so a
    module that is never imported is not checked."""

    def __init__(self, entry_path: pathlib.Path) -> None:
        self.base_dir = entry_path.parent
        self.paths: dict[str, pathlib.Path] = {"__main__": entry_path}
        self.trees: dict[str, ast.Module] = {
            q: ast.Module(body=[], type_ignores=[]) for q in PREDEFINED_MODULES
        }
        self.names = set(self.trees) | set(self.paths) | source_tree(self.base_dir)

    def path(self, name: str) -> pathlib.Path:
        if name not in self.paths:
            found = is_module(name, self.base_dir)
            assert found is not None
            self.paths[name] = found
        return self.paths[name]

    def __getitem__(self, name: str) -> ast.Module:
        if name not in self.names:
            raise KeyError(name)
        if name not in self.trees:
            self.trees[name] = parse(self.path(name))
        return self.trees[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.names)

    def __len__(self) -> int:
        return len(self.names)


def check_program(entry_path: pathlib.Path) -> IllFormed | syntax.Unsupported | None:
    program = Program(entry_path)
    try:
        check_module(program["__main__"], program, "__main__")
        return None
    except IllFormedModule as e:
        e.msg = f"{program.path(e.module or '__main__')}: {e.msg}"
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
