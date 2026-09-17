import ast
import sys
from collections.abc import Mapping
from dataclasses import replace

import reasons
import syntax
from aux import (
    assigns_body,
    assigns_stmt,
    split_imports,
    statements,
)
from classes import ClassTable
from contexts import (
    BUILTINS,
    MAIN,
    PREDEFINED_MODULES,
    Context,
    ContextEntry,
    ModuleContext,
    ModuleLoaded,
    ModuleStub,
    Status,
    extend_context,
    override_context,
    predefined_context,
)
from reasons import IllFormed, IllFormedModule, IllFormedProgram
from statements import check_top_seq
from type_syntax import (
    QualifiedName,
    Var,
    parent,
    parse_qualified,
    prefix_of,
    proper_prefix_of,
    proper_prefixes,
    qualified,
    root,
)


def name_assign(q: QualifiedName) -> ast.stmt:
    return ast.parse(f"__name__ = {str(q)!r}").body[0]


def loads_as(
    q: QualifiedName, theta: ContextEntry, mod_ctx: ModuleContext
) -> tuple[ContextEntry, ClassTable]:
    q_ = parent(q)
    if q_ is None:
        return theta, mod_ctx.Sigma
    gamma, Sigma = check_module(mod_ctx.M[q_], mod_ctx.M, q_, mod_ctx.Sigma)
    return loads_as(
        q_,
        ModuleLoaded(q_, extend_context(gamma, {q.parts[-1]: theta})),
        replace(mod_ctx, Sigma=Sigma),
    )


def check_imports_prefix(
    iotas: list[ast.stmt], mod_ctx: ModuleContext
) -> tuple[Context, ClassTable]:
    if len(iotas) == 0:
        return {}, mod_ctx.Sigma
    gamma, Sigma = check_import(iotas[0], mod_ctx)
    gamma_rest, sigma_rest = check_imports_prefix(
        iotas[1:], replace(mod_ctx, Sigma=Sigma)
    )
    return extend_context(gamma, gamma_rest), sigma_rest


def check_import(iota: ast.stmt, mod_ctx: ModuleContext) -> tuple[Context, ClassTable]:
    if isinstance(iota, ast.Import):
        q = parse_qualified(iota.names[0].name)
        if q not in mod_ctx.M:
            raise IllFormedModule(iota, reasons.UnknownModule(q))
        if proper_prefix_of(mod_ctx.q, q):
            raise IllFormedModule(
                iota,
                reasons.ImportOfContainedModule(
                    q, mod_ctx.q, f"from {parent(q)} import {q.parts[-1]}"
                ),
            )
        delta, Sigma = check_module(mod_ctx.M[q], mod_ctx.M, q, mod_ctx.Sigma)
        theta, Sigma = loads_as(
            q, ModuleLoaded(q, delta), replace(mod_ctx, Sigma=Sigma)
        )
        return {root(q): theta}, Sigma
    assert isinstance(iota, ast.ImportFrom) and iota.module is not None
    q = parse_qualified(iota.module)
    if q not in mod_ctx.M:
        raise IllFormedModule(iota, reasons.UnknownModule(q))
    delta, Sigma = check_module(mod_ctx.M[q], mod_ctx.M, q, mod_ctx.Sigma)
    Sigma = load_containing(
        [p for p in proper_prefixes(q) if not prefix_of(p, mod_ctx.q)],
        replace(mod_ctx, Sigma=Sigma),
    )
    return imports_seq(
        iota, [a.name for a in iota.names], q, delta, replace(mod_ctx, Sigma=Sigma)
    )


def load_containing(
    containing: list[QualifiedName], mod_ctx: ModuleContext
) -> ClassTable:
    if len(containing) == 0:
        return mod_ctx.Sigma
    _, Sigma = check_module(
        mod_ctx.M[containing[0]], mod_ctx.M, containing[0], mod_ctx.Sigma
    )
    return load_containing(containing[1:], replace(mod_ctx, Sigma=Sigma))


def submods(M: Mapping[QualifiedName, ast.Module], q: QualifiedName) -> Context:
    return {
        x: ModuleStub(qualified(q, x))
        for x in {q_.parts[len(q.parts)] for q_ in M if proper_prefix_of(q, q_)}
    }


def imports_seq(
    iota: ast.stmt,
    xs: list[Var],
    q: QualifiedName,
    gamma: Context,
    mod_ctx: ModuleContext,
) -> tuple[Context, ClassTable]:
    if len(xs) == 0:
        return {}, mod_ctx.Sigma
    theta, Sigma = imports(iota, xs[0], q, gamma, mod_ctx)
    gamma, Sigma_ = imports_seq(iota, xs[1:], q, gamma, replace(mod_ctx, Sigma=Sigma))
    return override_context({xs[0]: theta}, gamma), Sigma_


def imports(
    iota: ast.stmt, x: Var, q: QualifiedName, gamma: Context, mod_ctx: ModuleContext
) -> tuple[ContextEntry, ClassTable]:
    theta = gamma.get(x)
    if theta is None:
        raise IllFormedModule(iota, reasons.UnknownMember(x, q))
    if isinstance(theta, ModuleStub):
        members, Sigma = check_module(
            mod_ctx.M[theta.q], mod_ctx.M, theta.q, mod_ctx.Sigma
        )
        return ModuleLoaded(theta.q, members), Sigma
    if theta == Status.FF:
        raise IllFormedModule(iota, reasons.UnassignedMember(x, q))
    return theta, mod_ctx.Sigma


_signatures: dict[tuple[int, QualifiedName], Context] = {}
_loading: list[tuple[int, QualifiedName]] = []


def check_module(
    m: ast.Module,
    M: Mapping[QualifiedName, ast.Module],
    q: QualifiedName,
    Sigma: ClassTable,
) -> tuple[Context, ClassTable]:
    key = (id(M), q)
    gamma = _signatures.get(key)
    if gamma is not None:
        return gamma, Sigma
    if key in _loading:
        cycle = [str(q_) for _, q_ in _loading[_loading.index(key) :]] + [str(q)]
        raise IllFormedProgram(f"import cycle: {' -> '.join(cycle)}")
    _loading.append(key)
    try:
        gamma, Sigma = check_module_(m, M, q, Sigma)
    except IllFormedModule as e:
        if e.module is None:
            e.module = q
        raise
    finally:
        _loading.pop()
    _signatures[key] = gamma
    return gamma, Sigma


def check_module_(
    m: ast.Module,
    M: Mapping[QualifiedName, ast.Module],
    q: QualifiedName,
    Sigma: ClassTable,
) -> tuple[Context, ClassTable]:
    if q in PREDEFINED_MODULES:
        return predefined_context(q), Sigma
    iotas, stmts = split_imports(m.body)
    gamma, Sigma = check_imports_prefix(
        iotas, ModuleContext(gamma={}, M=M, q=q, Sigma=Sigma)
    )
    body = [name_assign(q)] + stmts
    mod_ctx = check_top_seq(
        statements(body),
        ModuleContext(
            gamma={**predefined_context(BUILTINS), **gamma}, M=M, q=q, Sigma=Sigma
        ),
    )
    check_submodule_names(m, gamma, body, M, q)
    return signature(body, mod_ctx, q), mod_ctx.Sigma


def check_submodule_names(
    m: ast.Module,
    gamma: Context,
    body: list[ast.stmt],
    M: Mapping[QualifiedName, ast.Module],
    q: QualifiedName,
) -> None:
    xs = sorted((set(gamma) | assigns_body(body)) & set(submods(M, q)))
    if len(xs) > 0:
        x = xs[0]
        node = find_binder(m.body, x)
        assert node is not None
        raise IllFormedModule(node, reasons.SubmoduleNameBound(x, q))


def binds_name(s: ast.stmt, x: str) -> bool:
    if isinstance(s, ast.Import):
        return root(parse_qualified(s.names[0].name)) == x
    if isinstance(s, ast.ImportFrom):
        return any(a.name == x for a in s.names)
    if isinstance(s, ast.ClassDef):
        return s.name == x
    return x in assigns_stmt(s)


def find_binder(stmts: list[ast.stmt], x: str) -> ast.stmt | None:
    return next((s for s in stmts if binds_name(s, x)), None)


def signature(
    body: list[ast.stmt], final_ctx: ModuleContext, q: QualifiedName
) -> Context:
    return override_context(
        submods(final_ctx.M, q), {x: final_ctx.gamma[x] for x in assigns_body(body)}
    )


def check_file(filename: str) -> IllFormed | syntax.Unsupported | None:
    with open(filename) as f:
        source = f.read()
    m = syntax.parse(source, filename)
    unsupported = syntax.check_syntax_module(m)
    if unsupported is not None:
        return unsupported
    M: dict[QualifiedName, ast.Module] = {
        p: ast.Module(body=[], type_ignores=[]) for p in PREDEFINED_MODULES
    }
    M[MAIN] = m
    try:
        check_module(m, M, MAIN, {})
        return None
    except IllFormed as e:
        return e


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
