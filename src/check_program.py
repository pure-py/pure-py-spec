import ast
import pathlib
import sys
from typing import Optional

import parse
import check_module
from check_module import IllFormed, IllFormedModule, Result


# Modules the runtime provides if the user has no file of the same name.
PREDEFINED_MODULES = {'builtins', 'math', 'sys', 'typing', 'dataclasses'}


class IllFormedProgram(IllFormed):
    exit_code = 4
    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


def _imports_of(tree: ast.Module) -> set[str]:
    """Module names appearing in top-level (or any) import statements in the module."""
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                result.add(node.module)
    return result


def _parents(name: str) -> set[str]:
    parts = name.split(".")
    return {".".join(parts[:i]) for i in range(1, len(parts))}


def _resolve(name: str, base_dir: pathlib.Path) -> Optional[pathlib.Path]:
    """Find the file backing module `name`: either `name.py` or `name/__init__.py`
    (dots in `name` become directory separators)."""
    stem = name.replace('.', '/')
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def _load(name: str, base_dir: pathlib.Path) -> tuple[Optional[ast.Module], Result]:
    """Load module `name` from base_dir. Returns (tree, ok()) on success;
    (None, error) if missing or fails to parse; (tree, error) if the syntactic
    subset rejects."""
    path = _resolve(name, base_dir)
    if path is None:
        return None, IllFormedProgram(f"module {name!r} not found under {base_dir}")
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as e:
        return None, IllFormedProgram(f"{path}: parse error: {e}")
    parse_err = parse.check_module(tree)
    if parse_err is not None:
        assert parse_err is not None
        return tree, IllFormedProgram(f"{path}: {parse_err.msg}")
    return tree, None


def _has_cycle(graph: dict[str, set[str]]) -> list[str]:
    """DFS cycle detection. Returns a cycle (as a list of names) if one exists, else []."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        color[node] = GRAY
        stack.append(node)
        for neighbour in graph.get(node, set()):
            if color.get(neighbour, WHITE) == GRAY:
                # cycle: from neighbour through stack back to neighbour
                idx = stack.index(neighbour)
                return stack[idx:] + [neighbour]
            if color.get(neighbour, WHITE) == WHITE:
                cycle = visit(neighbour)
                if len(cycle) > 0:
                    return cycle
        stack.pop()
        color[node] = BLACK
        return []

    for node in graph:
        if color[node] == WHITE:
            cycle = visit(node)
            if len(cycle) > 0:
                return cycle
    return []


def check_program(entry_path: pathlib.Path) -> Result:
    base_dir = entry_path.parent
    modules: dict[str, tuple[pathlib.Path, ast.Module]] = {}
    imports_by_module: dict[str, set[str]] = {}  # cached _imports_of(modules[name])
    queue: list[str] = [entry_path.stem, *PREDEFINED_MODULES]
    while queue:
        name = queue.pop()
        if name in modules:
            continue
        path = _resolve(name, base_dir)
        if path is None and name in PREDEFINED_MODULES:
            modules[name] = (pathlib.Path(f"<{name}>"), ast.Module(body=[], type_ignores=[]))
            imports_by_module[name] = set()
            continue
        tree, err = _load(name, base_dir)
        if err is not None:
            return err
        assert tree is not None and path is not None
        modules[name] = (path, tree)
        imports_by_module[name] = _imports_of(tree)
        for imp in imports_by_module[name]:
            queue.extend({imp} | _parents(imp))

    # Per-module well-formedness.
    for path, tree in modules.values():
        err = check_module.check_module(tree)
        if isinstance(err, IllFormedModule):
            err.msg = f"{path}: {err.msg}"
            return err

    # Acyclicity. (Resolution is already guaranteed by the walk loop above.)
    graph = {name: imps | _parents(name) | set().union(*(_parents(i) for i in imps))
             for name, imps in imports_by_module.items()}
    cycle = _has_cycle(graph)
    if len(cycle) > 0:
        return IllFormedProgram(f"import cycle: {' -> '.join(cycle)}")
    return None


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
