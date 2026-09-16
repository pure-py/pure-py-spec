import ast
import sys
from collections.abc import Mapping

import reasons
import syntax
from aux import (
    assigns_body,
    assigns_stmt,
    split_imports,
    statements,
)
from contexts import (
    PREDEFINED_MODULES,
    Context,
    ContextEntry,
    ModuleContext,
    ModuleLoaded,
    ModuleStub,
    Status,
    extend_context,
    predefined_context,
)
from reasons import IllFormed, IllFormedModule, IllFormedProgram
from statements import check_top_seq


def name_assign(q: str) -> ast.stmt:
    return ast.parse(f"__name__ = {q!r}").body[0]


def prefix_of(p: str, q: str) -> bool:
    return p == q or q.startswith(p + ".")


def proper_prefix_of(p: str, q: str) -> bool:
    return p != q and prefix_of(p, q)


def loads_as(q: str, theta: ContextEntry, mod_ctx: ModuleContext) -> ContextEntry:
    if "." not in q:
        return theta
    parent, x = q.rsplit(".", 1)
    parent_ctx = check_module(mod_ctx.M[parent], mod_ctx.M, parent)
    return loads_as(
        parent, ModuleLoaded(parent, extend_context(parent_ctx, {x: theta})), mod_ctx
    )


def proper_prefixes(q: str) -> list[str]:
    parts = q.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


def check_imports_prefix(prefix: list[ast.stmt], mod_ctx: ModuleContext) -> Context:
    if len(prefix) == 0:
        return {}
    return extend_context(
        check_import(prefix[0], mod_ctx), check_imports_prefix(prefix[1:], mod_ctx)
    )


def check_import(s: ast.stmt, mod_ctx: ModuleContext) -> Context:
    if isinstance(s, ast.Import):
        q = s.names[0].name
        if q not in mod_ctx.M:
            raise IllFormedModule(s, reasons.UnknownModule(q))
        if proper_prefix_of(mod_ctx.q, q):
            raise IllFormedModule(s, reasons.OwnDescendantImport(q, mod_ctx.q))
        delta = check_module(mod_ctx.M[q], mod_ctx.M, q)
        return {q.split(".")[0]: loads_as(q, ModuleLoaded(q, delta), mod_ctx)}
    assert isinstance(s, ast.ImportFrom) and s.module is not None
    if s.module not in mod_ctx.M:
        raise IllFormedModule(s, reasons.UnknownModule(s.module))
    delta = check_module(mod_ctx.M[s.module], mod_ctx.M, s.module)
    for p in proper_prefixes(s.module):
        if not prefix_of(p, mod_ctx.q):
            check_module(mod_ctx.M[p], mod_ctx.M, p)
    return {a.name: imports(s, a.name, s.module, delta, mod_ctx) for a in s.names}


def submods(M: Mapping[str, ast.Module], q: str) -> Context:
    return {
        x: ModuleStub(f"{q}.{x}")
        for x in {
            name[len(q) + 1 :].split(".")[0] for name in M if name.startswith(f"{q}.")
        }
    }


def imports(
    s: ast.stmt, x: str, q: str, gamma_src: Context, mod_ctx: ModuleContext
) -> ContextEntry:
    entry = gamma_src.get(x)
    if entry is None:
        raise IllFormedModule(s, reasons.UnknownMember(x, q))
    if isinstance(entry, ModuleStub):
        return ModuleLoaded(
            entry.q, check_module(mod_ctx.M[entry.q], mod_ctx.M, entry.q)
        )
    if entry == Status.FF:
        raise IllFormedModule(s, reasons.UnassignedMember(x, q))
    return entry


_signatures: dict[tuple[int, str], Context] = {}
_loading: list[tuple[int, str]] = []


def check_module(m: ast.Module, M: Mapping[str, ast.Module], q: str) -> Context:
    key = (id(M), q)
    cached = _signatures.get(key)
    if cached is not None:
        return cached
    if key in _loading:
        cycle = [name for _, name in _loading[_loading.index(key) :]] + [q]
        raise IllFormedProgram(f"import cycle: {' -> '.join(cycle)}")
    _loading.append(key)
    try:
        result = check_module_(m, M, q)
    except IllFormedModule as e:
        if e.module is None:
            e.module = q
        raise
    finally:
        _loading.pop()
    _signatures[key] = result
    return result


def check_module_(m: ast.Module, M: Mapping[str, ast.Module], q: str) -> Context:
    if q in PREDEFINED_MODULES:
        return predefined_context(q)
    imports, stmts = split_imports(m.body)
    gamma = check_imports_prefix(imports, ModuleContext(gamma={}, M=M, q=q))
    body = [name_assign(q)] + stmts
    mod_ctx = check_top_seq(
        statements(body),
        ModuleContext(gamma={**predefined_context("builtins"), **gamma}, M=M, q=q),
    )
    check_submodule_clash(m, gamma, body, M, q)
    return signature(body, mod_ctx, q)


def check_submodule_clash(
    m: ast.Module,
    gamma: Context,
    body: list[ast.stmt],
    M: Mapping[str, ast.Module],
    q: str,
) -> None:
    clash = sorted((set(gamma) | assigns_body(body)) & set(submods(M, q)))
    if len(clash) > 0:
        x = clash[0]
        node = find_binder(m.body, x)
        assert node is not None
        raise IllFormedModule(node, reasons.SubmoduleNameClash(x, f"{q}.{x}"))


def binds_name(s: ast.stmt, x: str) -> bool:
    if isinstance(s, ast.Import):
        return s.names[0].name.split(".")[0] == x
    if isinstance(s, ast.ImportFrom):
        return any(a.name == x for a in s.names)
    if isinstance(s, ast.ClassDef):
        return s.name == x
    return x in assigns_stmt(s)


def find_binder(stmts: list[ast.stmt], x: str) -> ast.stmt | None:
    return next((s for s in stmts if binds_name(s, x)), None)


def signature(body: list[ast.stmt], final_ctx: ModuleContext, q: str) -> Context:
    stubs: Context = submods(final_ctx.M, q)
    own = {name: final_ctx.gamma[name] for name in assigns_body(body)}
    return {**stubs, **own}


def module_result(
    m: ast.Module, M: Mapping[str, ast.Module], q: str
) -> IllFormed | None:
    try:
        check_module(m, M, q)
        return None
    except IllFormed as e:
        return e


def check_file(filename: str) -> IllFormed | syntax.Unsupported | None:
    with open(filename) as f:
        source = f.read()
    tree = syntax.parse(source, filename)
    unsupported = syntax.supported_module(tree)
    if unsupported is not None:
        return unsupported
    M: dict[str, ast.Module] = {
        p: ast.Module(body=[], type_ignores=[]) for p in PREDEFINED_MODULES
    }
    M["__main__"] = tree
    return module_result(tree, M, "__main__")


def format_result(result: IllFormed | syntax.Unsupported | None, filename: str) -> str:
    if isinstance(result, syntax.Unsupported):
        return syntax.format_result(result, filename)
    if result is None:
        return f"{filename}: ok"
    if isinstance(result, IllFormedModule):
        return f"{filename}:{result.line}:{result.col}: {result.msg}"
    return f"{filename}: {result.msg}"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: check_module.py <file.py> [<file.py> ...]")
        sys.exit(1)
    exit_code = 0
    for filename in sys.argv[1:]:
        result = check_file(filename)
        print(format_result(result, filename))
        if result is not None:
            exit_code = result.exit_code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
