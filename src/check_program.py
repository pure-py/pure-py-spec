import ast
import pathlib
import sys
from typing import Optional

import parse
from aux import annotate_seq_kinds
from check_module import check_module, has_cycle
from reasons import IllFormed, IllFormedModule, IllFormedProgram


PREDEFINED_MODULES = {'builtins', 'math', 'sys', 'typing', 'dataclasses'}


def imports(tree: ast.Module, base_dir: pathlib.Path) -> set[str]:
    froms = [(n.module, n.names) for n in ast.walk(tree)
             if isinstance(n, ast.ImportFrom) and n.module is not None]
    return ({a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            | {m for m, _ in froms}
            | {f'{m}.{a.name}' for m, names in froms for a in names
               if resolve(f'{m}.{a.name}', base_dir) is not None})


def parents(name: str) -> set[str]:
    parts = name.split(".")
    return {".".join(parts[:i]) for i in range(1, len(parts))}


def resolve(name: str, base_dir: pathlib.Path) -> Optional[pathlib.Path]:
    stem = name.replace('.', '/')
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def load(name: str, base_dir: pathlib.Path) -> ast.Module:
    path = resolve(name, base_dir)
    if path is None:
        raise IllFormedProgram(f"module {name!r} not found under {base_dir}")
    source = path.read_text()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        raise IllFormedProgram(f"{path}: parse error: {e}") from e
    parse_err = parse.check_module(tree)
    if parse_err is not None:
        raise IllFormedProgram(f"{path}: {parse_err.msg}")
    annotate_seq_kinds(tree, source)
    return tree


def check_program(entry_path: pathlib.Path) -> Optional[IllFormed]:
    try:
        walk_program(entry_path)
        return None
    except IllFormed as e:
        return e

def module_name(base_dir: pathlib.Path, path: pathlib.Path) -> tuple[str, ...]:
    rel = path.relative_to(base_dir)
    return rel.parent.parts if rel.name == '__init__.py' else rel.with_suffix('').parts

def source_tree(base_dir: pathlib.Path, entry_path: pathlib.Path) -> set[str]:
    parts = (module_name(base_dir, p) for p in base_dir.rglob('*.py') if p != entry_path)
    return {'.'.join(p) for p in parts if p}

Discovery = tuple[dict[str, tuple[pathlib.Path, ast.Module]], dict[str, set[str]]]

def with_parents(imps: set[str]) -> list[str]:
    return sorted({q for imp in imps for q in {imp} | parents(imp)})

def discover(queue: list[str], found: Discovery, base_dir: pathlib.Path) -> Discovery:
    if len(queue) == 0:
        return found
    name, rest = queue[0], queue[1:]
    modules, imports_by = found
    if name in modules:
        return discover(rest, found, base_dir)
    path = resolve(name, base_dir)
    if path is None and name in PREDEFINED_MODULES:
        return discover(rest, (modules | {name: (pathlib.Path(f"<{name}>"), ast.Module(body=[], type_ignores=[]))},
                               imports_by | {name: set()}), base_dir)
    tree = load(name, base_dir)
    assert path is not None
    imps = imports(tree, base_dir)
    return discover(rest + with_parents(imps),
                    (modules | {name: (path, tree)}, imports_by | {name: imps}), base_dir)

def walk_program(entry_path: pathlib.Path) -> None:
    base_dir = entry_path.parent
    entry_tree = load(entry_path.stem, base_dir)
    entry_imports = imports(entry_tree, base_dir)
    queue = [*sorted(PREDEFINED_MODULES), *sorted(source_tree(base_dir, entry_path)), *with_parents(entry_imports)]
    modules, imports_by_module = discover(queue, ({'__main__': (entry_path, entry_tree)},
                                                  {'__main__': entry_imports}), base_dir)

    graph = {name: imps | parents(name) for name, imps in imports_by_module.items()}
    cycle = has_cycle(graph)
    if len(cycle) > 0:
        raise IllFormedProgram(f"import cycle: {' -> '.join(cycle)}")

    M = {name: tree for name, (_, tree) in modules.items()}
    try:
        check_module(modules['__main__'][1], M, '__main__')
    except IllFormedModule as e:
        path = modules[e.module or '__main__'][0]
        e.msg = f"{path}: {e.msg}"
        raise


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
