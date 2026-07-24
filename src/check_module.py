from __future__ import annotations

import ast
import sys
from typing import Optional

import reasons
from reasons import IllFormed, IllFormedModule, IllFormedProgram
from contexts import (Context, ContextEntry, ModuleContext, ModuleLoaded, ModuleStub,
                      PREDEFINED_MEMBERS, PREDEFINED_MODULES, Status, TyReturns, extend_context)
from aux import (annotate_seq_kinds, assigns_block, assigns_stmt, find_import,
                 find_nested_import, split_imports)
from well_formed import check_block, result_type_of_block

def name_assign(q: str) -> ast.stmt:
    return ast.parse(f'__name__ = {q!r}').body[0]

def prefix_of(p: str, q: str) -> bool:
    return p == q or q.startswith(p + '.')

def proper_prefix_of(p: str, q: str) -> bool:
    return p != q and prefix_of(p, q)

def loads_to(bound: str, q: str, theta: ContextEntry, ctx: ModuleContext) -> ContextEntry:
    if '.' not in q:
        return theta
    parent, x = q.rsplit('.', 1)
    if prefix_of(parent, bound):
        return theta
    parent_ctx = check_module(ctx.M[parent], ctx.M, parent)
    return loads_to(bound, parent, ModuleLoaded(parent, extend_context(parent_ctx, {x: theta})), ctx)

def imports(s: ast.ImportFrom, gamma_src: Context, ctx: ModuleContext) -> Context:
    assert s.module is not None
    return {a.name: imported_entry(s, a.name, s.module, gamma_src, ctx) for a in s.names}

def check_imports_prefix(prefix: list[ast.stmt], ctx: ModuleContext) -> Context:
    if len(prefix) == 0:
        return {}
    return extend_context(import_bindings(prefix[0], ctx), check_imports_prefix(prefix[1:], ctx))

def import_bindings(s: ast.stmt, ctx: ModuleContext) -> Context:
    if isinstance(s, ast.Import):
        q = s.names[0].name
        if q not in ctx.M:
            raise IllFormedModule(s, reasons.UnknownModule(q))
        if proper_prefix_of(ctx.q, q):
            raise IllFormedModule(s, reasons.OwnDescendantImport(q, ctx.q))
        delta = check_module(ctx.M[q], ctx.M, q)
        return {q.split('.')[0]: loads_to('', q, ModuleLoaded(q, delta), ctx)}
    assert isinstance(s, ast.ImportFrom)
    if len(s.names) == 0:
        raise IllFormedModule(s, reasons.EmptyFromImport())
    assert s.module is not None
    if s.module not in ctx.M:
        raise IllFormedModule(s, reasons.UnknownModule(s.module))
    delta = check_module(ctx.M[s.module], ctx.M, s.module)
    loads_to(ctx.q, s.module, ModuleLoaded(s.module, delta), ctx)
    return imports(s, delta, ctx)

def submodules(M: dict[str, ast.Module], q: str) -> Context:
    return {x: ModuleStub(f'{q}.{x}')
            for x in {name[len(q) + 1:].split('.')[0] for name in M if name.startswith(f'{q}.')}}

def imported_entry(s: ast.stmt, x: str, q: str, gamma_src: Context,
                   ctx: ModuleContext) -> ContextEntry:
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

def has_cycle(graph: dict[str, set[str]]) -> list[str]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        color[node] = GRAY
        stack.append(node)
        for neighbour in graph.get(node, set()):
            if color.get(neighbour, WHITE) == GRAY:
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

_module_contexts: dict[tuple[int, str], Context] = {}

def check_module(m: ast.Module, M: dict[str, ast.Module], q: str) -> Context:
    key = (id(M), q)
    cached = _module_contexts.get(key)
    if cached is not None:
        return cached
    try:
        result = check_module_(m, M, q)
    except IllFormedModule as e:
        if e.module is None:
            e.module = q
        raise
    _module_contexts[key] = result
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
    final_ctx = check_block(body, ModuleContext(gamma=gamma0, M=M, q=q), module_body=True)
    if rest and isinstance(result_type_of_block(rest), TyReturns):
        raise IllFormedModule(rest[0], reasons.TopLevelReturn())
    check_submodule_clash(m, gamma0, body, M, q)
    return module_context(body, final_ctx, q)

def check_submodule_clash(m: ast.Module, gamma0: Context, body: list[ast.stmt],
                          M: dict[str, ast.Module], q: str) -> None:
    clash = sorted((set(gamma0) | own_members(body, q)) & set(submodules(M, q)))
    if clash:
        x = clash[0]
        node = find_binder(m.body, x)
        assert node is not None
        raise IllFormedModule(node, reasons.SubmoduleNameClash(x, f'{q}.{x}'))

def binds_name(s: ast.stmt, x: str) -> bool:
    if isinstance(s, ast.Import):
        return s.names[0].name.split('.')[0] == x
    if isinstance(s, ast.ImportFrom):
        return any(a.name == x for a in s.names)
    if isinstance(s, ast.ClassDef):
        return s.name == x
    return x in assigns_stmt(s)

def find_binder(stmts: list[ast.stmt], x: str) -> Optional[ast.stmt]:
    return next((s for s in stmts if binds_name(s, x)), None)

def module_context(body: list[ast.stmt], final_ctx: ModuleContext, q: str) -> Context:
    stubs: Context = submodules(final_ctx.M, q)
    if q in PREDEFINED_MEMBERS:
        own: Context = {name: Status.TT for name in PREDEFINED_MEMBERS[q] | {'__name__'}}
    else:
        own = {name: final_ctx.gamma[name] for name in own_members(body, q)}
    return {**stubs, **own}

def module_result(m: ast.Module, M: dict[str, ast.Module], q: str) -> Optional[IllFormed]:
    try:
        check_module(m, M, q)
        return None
    except IllFormed as e:
        return e

def imported_modules(tree: ast.Module) -> set[str]:
    return ({a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            | {n.module for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.module is not None})

def check_file(filename: str) -> Optional[IllFormed]:
    source = open(filename).read()
    tree = ast.parse(source, filename=filename)
    annotate_seq_kinds(tree, source)
    M: dict[str, ast.Module] = {p: ast.Module(body=[], type_ignores=[]) for p in PREDEFINED_MODULES}
    M['__main__'] = tree
    cycle = has_cycle({'__main__': imported_modules(tree)})
    if len(cycle) > 0:
        return IllFormedProgram(f"import cycle: {' -> '.join(cycle)}")
    return module_result(tree, M, '__main__')

def format_result(result: Optional[IllFormed], filename: str) -> str:
    if result is None:
        return f'{filename}: ok'
    if isinstance(result, IllFormedModule):
        return f'{filename}:{result.line}:{result.col}: {result.msg}'
    return f'{filename}: {result.msg}'

def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: check_module.py <file.py> [<file.py> ...]')
        sys.exit(1)
    exit_code = 0
    for filename in sys.argv[1:]:
        result = check_file(filename)
        print(format_result(result, filename))
        if result is not None:
            exit_code = result.exit_code
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
