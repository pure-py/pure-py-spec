import ast
import pathlib
import sys
from typing import Optional

import parse
from check_module import IllFormed, IllFormedModule, has_cycle, walk_module


# Modules the runtime provides if the user has no file of the same name.
PREDEFINED_MODULES = {'builtins', 'math', 'sys', 'typing', 'dataclasses'}


class IllFormedProgram(IllFormed):
    exit_code = 4
    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


def imports_of(tree: ast.Module) -> set[str]:
    """Module names appearing in top-level (or any) import statements in the module."""
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                result.add(node.module)
    return result


def parents(name: str) -> set[str]:
    parts = name.split(".")
    return {".".join(parts[:i]) for i in range(1, len(parts))}


def resolve(name: str, base_dir: pathlib.Path) -> Optional[pathlib.Path]:
    """Find the file backing module `name`: either `name.py` or `name/__init__.py`
    (dots in `name` become directory separators)."""
    stem = name.replace('.', '/')
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def load(name: str, base_dir: pathlib.Path) -> ast.Module:
    """Load and syntactically-check module `name`. Raises IllFormedProgram if
    the file is missing, fails to parse, or violates the PurePy subset."""
    path = resolve(name, base_dir)
    if path is None:
        raise IllFormedProgram(f"module {name!r} not found under {base_dir}")
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as e:
        raise IllFormedProgram(f"{path}: parse error: {e}") from e
    parse_err = parse.check_module(tree)
    if parse_err is not None:
        raise IllFormedProgram(f"{path}: {parse_err.msg}")
    return tree


def check_program(entry_path: pathlib.Path) -> Optional[IllFormed]:
    try:
        walk_program(entry_path)
        return None
    except IllFormed as e:
        return e

def walk_program(entry_path: pathlib.Path) -> None:
    base_dir = entry_path.parent
    modules: dict[str, tuple[pathlib.Path, ast.Module]] = {}
    imports_by_module: dict[str, set[str]] = {}  # cached imports_of(modules[name])
    queue: list[str] = [entry_path.stem, *PREDEFINED_MODULES]
    while queue:
        name = queue.pop()
        if name in modules:
            continue
        path = resolve(name, base_dir)
        if path is None and name in PREDEFINED_MODULES:
            modules[name] = (pathlib.Path(f"<{name}>"), ast.Module(body=[], type_ignores=[]))
            imports_by_module[name] = set()
            continue
        tree = load(name, base_dir)
        assert path is not None
        modules[name] = (path, tree)
        imports_by_module[name] = imports_of(tree)
        for imp in imports_by_module[name]:
            queue.extend({imp} | parents(imp))

    # Per-module well-formedness.
    for path, tree in modules.values():
        try:
            walk_module(tree)
        except IllFormedModule as e:
            e.msg = f"{path}: {e.msg}"
            raise

    # Acyclicity. (Resolution is already guaranteed by the walk loop above.)
    graph = {name: imps | parents(name) | set().union(*(parents(i) for i in imps))
             for name, imps in imports_by_module.items()}
    cycle = has_cycle(graph)
    if len(cycle) > 0:
        raise IllFormedProgram(f"import cycle: {' -> '.join(cycle)}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: check_program.py <entry-file>")
        sys.exit(1)
    entry = pathlib.Path(sys.argv[1])
    result = check_program(entry)
    if result is None:
        print(f"{entry}: ok")
        sys.exit(0)
    assert result is not None
    print(result.msg)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
