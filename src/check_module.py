import ast
import sys

import reasons
import syntax
from aux import (
    BlockElement,
    assigns_block,
    assigns_elements,
    assigns_stmt,
    captures_element,
    elements_of_block,
    find_first_reassigning,
    find_import,
    find_nested_import,
    own_fields,
    split_imports,
)
from blocks import block_element_result_type, check_element, next_ctx_after
from contexts import (
    PREDEFINED_MEMBERS,
    PREDEFINED_MODULES,
    ClassEntry,
    Context,
    ContextEntry,
    ModuleContext,
    ModuleLoaded,
    ModuleStub,
    Returns,
    Status,
    extend_context,
    fields,
    override_gamma,
    predefined_context,
)
from reasons import IllFormed, IllFormedModule, IllFormedProgram


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
    assert isinstance(s, ast.ImportFrom)
    if len(s.names) == 0:
        raise IllFormedModule(s, reasons.EmptyFromImport())
    assert s.module is not None
    if s.module not in ctx.M:
        raise IllFormedModule(s, reasons.UnknownModule(s.module))
    delta = check_module(ctx.M[s.module], ctx.M, s.module)
    for p in proper_prefixes(s.module):
        if not prefix_of(p, ctx.q):
            check_module(ctx.M[p], ctx.M, p)
    return imports(s, delta, ctx)


def submods(M: dict[str, ast.Module], q: str) -> Context:
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
        return PREDEFINED_MEMBERS[q]
    return assigns_block(body) | {s.name for s in body if isinstance(s, ast.ClassDef)}


_signatures: dict[tuple[int, str], Context] = {}
_loading: list[tuple[int, str]] = []


def check_statements(items: list[BlockElement], ctx: ModuleContext) -> ModuleContext:
    if len(items) == 0:
        return ctx
    head, tail = items[0], items[1:]
    if isinstance(head, ast.ClassDef):
        check_class_decl(head, ctx.gamma, ctx.q)
    else:
        check_element(head, ctx)
    if isinstance(block_element_result_type(head), Returns):
        node: ast.AST = head[0] if isinstance(head, list) else head
        raise IllFormedModule(node, reasons.TopLevelReturn())
    reassigned = captures_element(head) & assigns_elements(tail)
    if reassigned:
        name = min(reassigned)
        ra_node = find_first_reassigning(tail, reassigned)
        assert ra_node is not None
        raise IllFormedModule(ra_node, reasons.CapturedReassignment(name))
    return check_statements(tail, next_statement_ctx(head, ctx))


def next_statement_ctx(head: BlockElement, ctx: ModuleContext) -> ModuleContext:
    next_ctx = next_ctx_after(head, ctx)
    if isinstance(head, ast.ClassDef):
        return override_gamma(
            next_ctx, {head.name: class_entry_for(head, ctx.q, ctx.gamma)}
        )
    return next_ctx


def class_entry_for(node: ast.ClassDef, q: str, context: Context) -> ClassEntry:
    base = (
        node.bases[0].id if node.bases and isinstance(node.bases[0], ast.Name) else None
    )
    return ClassEntry(
        context=context,
        name=f"{q}.{node.name}",
        own_fields=tuple(own_fields(node)),
        base=base,
    )


def check_class_decl(node: ast.ClassDef, gamma: Context, q: str) -> None:
    if isinstance(gamma.get(node.name), ClassEntry):
        raise IllFormedModule(node, reasons.DuplicateClassName(node.name, q))
    names = own_fields(node)
    dup = next((n for i, n in enumerate(names) if n in names[:i]), None)
    if dup is not None:
        raise IllFormedModule(node, reasons.DuplicateFieldName(dup, node.name))
    if len(node.bases) == 0:
        return
    base = node.bases[0]
    assert isinstance(base, ast.Name)
    entry = gamma.get(base.id)
    if not isinstance(entry, ClassEntry) or entry.name.rsplit(".", 1)[0] != q:
        raise IllFormedModule(node, reasons.UnknownBaseClass(base.id))
    clash = set(names) & set(fields(entry))
    if len(clash) > 0:
        raise IllFormedModule(node, reasons.InheritedFieldClash(min(clash), base.id))


def check_module(m: ast.Module, M: dict[str, ast.Module], q: str) -> Context:
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


def check_module_(m: ast.Module, M: dict[str, ast.Module], q: str) -> Context:
    nested = find_nested_import(m.body)
    if nested is not None:
        raise IllFormedModule(nested, reasons.NonTopLevelImport())
    prefix, rest = split_imports(m.body)
    stray = find_import(rest)
    if stray is not None:
        raise IllFormedModule(stray, reasons.ImportAfterStatement())
    gamma0 = check_imports_prefix(prefix, ModuleContext(gamma={}, M=M, q=q))
    body = [name_assign(q)] + rest
    gamma1 = {**predefined_context("builtins"), **gamma0}
    final_ctx = check_statements(
        elements_of_block(body), ModuleContext(gamma=gamma1, M=M, q=q)
    )
    check_submodule_clash(m, gamma0, body, M, q)
    return signature(body, final_ctx, q)


def check_submodule_clash(
    m: ast.Module,
    gamma0: Context,
    body: list[ast.stmt],
    M: dict[str, ast.Module],
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


def module_result(m: ast.Module, M: dict[str, ast.Module], q: str) -> IllFormed | None:
    try:
        check_module(m, M, q)
        return None
    except IllFormed as e:
        return e


def check_file(filename: str) -> IllFormed | None:
    with open(filename) as f:
        source = f.read()
    tree = syntax.parse(source, filename)
    M: dict[str, ast.Module] = {
        p: ast.Module(body=[], type_ignores=[]) for p in PREDEFINED_MODULES
    }
    M["__main__"] = tree
    return module_result(tree, M, "__main__")


def format_result(result: IllFormed | None, filename: str) -> str:
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
