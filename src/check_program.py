import ast
import pathlib
import sys

import syntax
from check_module import check_module, proper_prefixes
from contexts import PREDEFINED_MODULES
from reasons import IllFormed, IllFormedModule, IllFormedProgram


def import_targets(tree: ast.Module, base_dir: pathlib.Path) -> set[str]:
    froms = [
        (n.module, n.names)
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module is not None
    ]
    return (
        {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        | {m for m, _ in froms}
        | {
            f"{m}.{a.name}"
            for m, names in froms
            for a in names
            if is_module(f"{m}.{a.name}", base_dir) is not None
        }
    )


def is_module(name: str, base_dir: pathlib.Path) -> pathlib.Path | None:
    stem = name.replace(".", "/")
    for candidate in (base_dir / f"{stem}.py", base_dir / stem / "__init__.py"):
        if candidate.exists():
            return candidate
    return base_dir / stem if (base_dir / stem).is_dir() else None


def load(name: str, base_dir: pathlib.Path) -> ast.Module:
    path = is_module(name, base_dir)
    if path is None:
        raise IllFormedProgram(f"module {name!r} not found under {base_dir}")
    if path.is_dir():
        return ast.Module(body=[], type_ignores=[])
    source = path.read_text()
    try:
        tree = syntax.parse(source, str(path))
    except SyntaxError as e:
        raise IllFormedProgram(f"{path}: parse error: {e}") from e
    parse_err = syntax.check_module(tree)
    if parse_err is not None:
        raise IllFormedProgram(f"{path}: {parse_err.msg}")
    return tree


def check_program(entry_path: pathlib.Path) -> IllFormed | None:
    try:
        walk_program(entry_path)
        return None
    except IllFormed as e:
        return e


def module_name(base_dir: pathlib.Path, path: pathlib.Path) -> tuple[str, ...]:
    rel = path.relative_to(base_dir)
    return rel.parent.parts if rel.name == "__init__.py" else rel.with_suffix("").parts


def source_tree(base_dir: pathlib.Path, entry_path: pathlib.Path) -> set[str]:
    parts = (
        module_name(base_dir, p)
        for p in base_dir.rglob("*.py")
        if p != entry_path and "__pycache__" not in p.parts
    )
    names = {".".join(p) for p in parts if p}
    return {n for name in names for n in {name, *proper_prefixes(name)}}


Discovery = tuple[dict[str, tuple[pathlib.Path, ast.Module]], dict[str, set[str]]]


def with_proper_prefixes(imps: set[str]) -> list[str]:
    return sorted({q for imp in imps for q in {imp, *proper_prefixes(imp)}})


def discover(queue: list[str], found: Discovery, base_dir: pathlib.Path) -> Discovery:
    if len(queue) == 0:
        return found
    name, rest = queue[0], queue[1:]
    modules, imports_by = found
    if name in modules:
        return discover(rest, found, base_dir)
    path = is_module(name, base_dir)
    if path is None and name in PREDEFINED_MODULES:
        return discover(
            rest,
            (
                modules
                | {
                    name: (
                        pathlib.Path(f"<{name}>"),
                        ast.Module(body=[], type_ignores=[]),
                    )
                },
                imports_by | {name: set()},
            ),
            base_dir,
        )
    tree = load(name, base_dir)
    assert path is not None
    imps = import_targets(tree, base_dir)
    return discover(
        rest + with_proper_prefixes(imps),
        (modules | {name: (path, tree)}, imports_by | {name: imps}),
        base_dir,
    )


def walk_program(entry_path: pathlib.Path) -> None:
    base_dir = entry_path.parent
    entry_tree = load(entry_path.stem, base_dir)
    entry_imports = import_targets(entry_tree, base_dir)
    queue = [
        *sorted(PREDEFINED_MODULES),
        *sorted(source_tree(base_dir, entry_path)),
        *with_proper_prefixes(entry_imports),
    ]
    modules, _ = discover(
        queue,
        ({"__main__": (entry_path, entry_tree)}, {"__main__": entry_imports}),
        base_dir,
    )

    M = {name: tree for name, (_, tree) in modules.items()}
    try:
        check_module(modules["__main__"][1], M, "__main__")
    except IllFormedModule as e:
        path = modules[e.module or "__main__"][0]
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
