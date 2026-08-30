import ast
import sys
from collections.abc import Mapping

import reasons
import syntax
from aux import (
    assigns_body,
    assigns_stmt,
    first_return,
    split_imports,
    statements,
)
from contexts import (
    PREDEFINED_MEMBERS,
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
from statements import check_seq


def name_assign(q: str) -> ast.stmt:
    return ast.parse(f"__name__ = {q!r}").body[0]


def prefix_of(p: str, q: str) -> bool:
    return p == q or q.startswith(p + ".")


def proper_prefix_of(p: str, q: str) -> bool:
    return p != q and prefix_of(p, q)


def loads_as(q: str, theta: ContextEntry, ctx: ModuleContext) -> ContextEntry:
    if "." not in q:
        return theta
    parent, x = q.rsplit(".", 1)
    parent_ctx = check_module(ctx.M[parent], ctx.M, parent)
    return loads_as(
        parent, ModuleLoaded(parent, extend_context(parent_ctx, {x: theta})), ctx
    )


def proper_prefixes(q: str) -> list[str]:
    parts = q.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


def imports(s: ast.ImportFrom, gamma_src: Context, ctx: ModuleContext) -> Context:
    assert s.module is not None
    return {
        a.name: imported_entry(s, a.name, s.module, gamma_src, ctx) for a in s.names
    }


def check_imports_prefix(prefix: list[ast.stmt], ctx: ModuleContext) -> Context:
    if len(prefix) == 0:
        return {}
    return extend_context(
        import_bindings(prefix[0], ctx), check_imports_prefix(prefix[1:], ctx)
    )


def import_bindings(s: ast.stmt, ctx: ModuleContext) -> Context:
    if isinstance(s, ast.Import):
        q = s.names[0].name
        if q not in ctx.M:
            raise IllFormedModule(s, reasons.UnknownModule(q))
        if proper_prefix_of(ctx.q, q):
            raise IllFormedModule(s, reasons.OwnDescendantImport(q, ctx.q))
        delta = check_module(ctx.M[q], ctx.M, q)
        return {q.split(".")[0]: loads_as(q, ModuleLoaded(q, delta), ctx)}
    assert isinstance(s, ast.ImportFrom) and s.module is not None
    if s.module not in ctx.M:
        raise IllFormedModule(s, reasons.UnknownModule(s.module))
    delta = check_module(ctx.M[s.module], ctx.M, s.module)
    for p in proper_prefixes(s.module):
        if not prefix_of(p, ctx.q):
            check_module(ctx.M[p], ctx.M, p)
    return imports(s, delta, ctx)


def submods(M: Mapping[str, ast.Module], q: str) -> Context:
    return {
        x: ModuleStub(f"{q}.{x}")
        for x in {
            name[len(q) + 1 :].split(".")[0] for name in M if name.startswith(f"{q}.")
        }
    }


def imported_entry(
    s: ast.stmt, x: str, q: str, gamma_src: Context, ctx: ModuleContext
) -> ContextEntry:
    entry = gamma_src.get(x)
    if entry is None:
        raise IllFormedModule(s, reasons.UnknownMember(x, q))
    if isinstance(entry, ModuleStub):
        return ModuleLoaded(entry.q, check_module(ctx.M[entry.q], ctx.M, entry.q))
    if entry == Status.FF:
        raise IllFormedModule(s, reasons.UnassignedMember(x, q))
    return entry


def own_members(body: list[ast.stmt], q: str) -> set[str]:
    if q in PREDEFINED_MEMBERS:
        return set(PREDEFINED_MEMBERS[q])
    return assigns_body(body)


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
    prefix, rest = split_imports(m.body)
    gamma0 = check_imports_prefix(prefix, ModuleContext(gamma={}, M=M, q=q))
    body = [name_assign(q)] + rest
    gamma1 = {**predefined_context("builtins"), **gamma0}
    returning = first_return(body)
    if returning is not None:  # no return rule applies with an empty return type
        raise IllFormedModule(returning, reasons.TopLevelReturn())
    items = statements(body)
    _, final_ctx = check_seq(items, ModuleContext(gamma=gamma1, M=M, q=q))
    check_submodule_clash(m, gamma0, body, M, q)
    return signature(body, final_ctx, q)


def check_submodule_clash(
    m: ast.Module,
    gamma0: Context,
    body: list[ast.stmt],
    M: Mapping[str, ast.Module],
    q: str,
) -> None:
    clash = sorted((set(gamma0) | own_members(body, q)) & set(submods(M, q)))
    if clash:
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
    if q in PREDEFINED_MEMBERS:
        own: Context = predefined_context(q)
    else:
        own = {name: final_ctx.gamma[name] for name in own_members(body, q)}
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
