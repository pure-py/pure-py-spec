import ast
import pathlib
import sys
from typing import Optional

import purepy_parse
import purepy_check
from purepy_check import Error, Result, ok, is_ok


ILL_FORMED_PROGRAM = 4


def _program_error(msg: str) -> Error:
    return Error(line=None, col=None, msg=msg, kind=ILL_FORMED_PROGRAM)


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


def _load(name: str, base_dir: pathlib.Path) -> tuple[Optional[ast.Module], Result]:
    """Load module `name` from base_dir. Returns (tree, ok()) on success;
    (None, error) if missing or fails to parse; (tree, error) if the syntactic
    subset rejects."""
    path = base_dir / f"{name.replace('.', '/')}.py"
    if not path.exists():
        return None, _program_error(f"module {name!r} not found at {path}")
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as e:
        return None, _program_error(f"{path}: parse error: {e}")
    parse_err = purepy_parse.check_module(tree)
    if not purepy_parse.is_ok(parse_err):
        assert parse_err is not None
        return tree, _program_error(f"{path}: {parse_err.msg}")
    return tree, ok()


def _has_cycle(graph: dict[str, set[str]]) -> Optional[list[str]]:
    """DFS cycle detection. Returns a cycle (as a list of names) if one exists, else None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    stack: list[str] = []

    def visit(node: str) -> Optional[list[str]]:
        color[node] = GRAY
        stack.append(node)
        for neighbour in graph.get(node, set()):
            if color.get(neighbour, WHITE) == GRAY:
                # cycle: from neighbour through stack back to neighbour
                idx = stack.index(neighbour)
                return stack[idx:] + [neighbour]
            if color.get(neighbour, WHITE) == WHITE:
                cycle = visit(neighbour)
                if cycle is not None:
                    return cycle
        stack.pop()
        color[node] = BLACK
        return None

    for node in graph:
        if color[node] == WHITE:
            cycle = visit(node)
            if cycle is not None:
                return cycle
    return None


def check_program(entry_path: pathlib.Path) -> Result:
    base_dir = entry_path.parent
    modules: dict[str, ast.Module] = {}
    imports_by_module: dict[str, set[str]] = {}  # cached _imports_of(modules[name])
    queue: list[str] = [entry_path.stem]
    while queue:
        name = queue.pop()
        if name in modules:
            continue
        tree, err = _load(name, base_dir)
        if not is_ok(err):
            return err
        assert tree is not None
        modules[name] = tree
        imports_by_module[name] = _imports_of(tree)
        for imp in imports_by_module[name]:
            queue.extend({imp} | _parents(imp))

    # Per-module well-formedness.
    for tree in modules.values():
        err = purepy_check.check_module(tree)
        if not is_ok(err):
            return err

    # Acyclicity. (Resolution is already guaranteed by the walk loop above.)
    graph = {name: imps | _parents(name) | set().union(*(_parents(i) for i in imps))
             for name, imps in imports_by_module.items()}
    cycle = _has_cycle(graph)
    if cycle is not None:
        return _program_error(f"import cycle: {' -> '.join(cycle)}")

    return ok()


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: purepy_check_program.py <entry-file>")
        sys.exit(1)
    entry = pathlib.Path(sys.argv[1])
    result = check_program(entry)
    if is_ok(result):
        print(f"{entry}: ok")
        sys.exit(0)
    assert result is not None
    print(f"{entry}: {result.msg}")
    sys.exit(result.kind)


if __name__ == "__main__":
    main()
