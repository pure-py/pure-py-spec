import ast
from dataclasses import replace

import reasons
from aux import (
    Statement,
    assign_targets,
    assigns_body,
    binds_quals,
    captures_e_list,
    captures_quals,
    declares_body,
    dict_keys,
    own_fields,
    pattern_bound,
    qualified_name,
    redeclaration,
    statements,
    target_name,
    type_expr,
)
from classes import (
    Class,
    ClassTable,
    ClassTableEntry,
    declared_type,
    field_map,
    field_type,
    fields,
    short_name,
)
from contexts import (
    Assigns,
    DeclTy,
    ModuleContext,
    ModuleLoaded,
    ModuleStub,
    PredefinedName,
    Returns,
    StaticOutcome,
    Unbound,
    VarContext,
    assigned_type,
    class_of_name,
    entry_of,
    is_assigned,
    merge_outcomes,
    module_of,
    override_gamma,
    override_outcomes,
    resolve_name,
)
from match import match_shapes, seq_safe
from operators import (
    BINARY_NAMES,
    UNARY_NAMES,
    minimum,
    overloads_binary,
    overloads_unary,
)
from reasons import IllFormedModule
from shapes import shapes
from subtyping import join_seq, subtype
from syntax import PatList
from type_syntax import (
    CallableExpr,
    CallableType,
    ClassName,
    ClassType,
    DictExpr,
    DictType,
    ListExpr,
    ListType,
    LiteralType,
    Primitive,
    QualifiedName,
    TupleExpr,
    TupleType,
    Type,
    TypeExpr,
    UnionExpr,
    UnionType,
    Var,
    base_type,
    literal_type,
    qualified,
)


def signature(d: ast.FunctionDef, mod_ctx: ModuleContext) -> CallableType:
    return CallableType(
        tuple(resolve_type(type_expr(a.annotation), a, mod_ctx) for a in d.args.args),
        resolve_type(type_expr(d.returns), d, mod_ctx),
    )


def parameters(d: ast.FunctionDef, mod_ctx: ModuleContext) -> VarContext:
    return {a.arg: resolve_type(type_expr(a.annotation), a, mod_ctx) for a in d.args.args}


def resolve_type(psi: TypeExpr, node: ast.AST, mod_ctx: ModuleContext) -> Type:
    match psi:
        case Primitive():
            check_in_scope(psi.value, node, mod_ctx)
            return psi
        case LiteralType():
            check_in_scope("Literal", node, mod_ctx)
            return psi
        case ClassName(q):
            c = resolve_name(q, mod_ctx)
            if isinstance(c, Unbound):
                raise IllFormedModule(node, reasons.UnboundName(str(q)))
            if not isinstance(c, Class):
                raise IllFormedModule(node, reasons.NotClass(q))
            return ClassType(c)
        case ListExpr(psi_):
            check_in_scope("list", node, mod_ctx)
            return ListType(resolve_type(psi_, node, mod_ctx))
        case DictExpr(psi_):
            check_in_scope("dict", node, mod_ctx)
            check_in_scope("str", node, mod_ctx)
            return DictType(resolve_type(psi_, node, mod_ctx))
        case TupleExpr(psis):
            check_in_scope("tuple", node, mod_ctx)
            return TupleType(tuple(resolve_type(c, node, mod_ctx) for c in psis))
        case CallableExpr(psis, psi_):
            check_in_scope("Callable", node, mod_ctx)
            return CallableType(
                tuple(resolve_type(p, node, mod_ctx) for p in psis),
                resolve_type(psi_, node, mod_ctx),
            )
        case UnionExpr():
            return UnionType(
                resolve_type(psi.left, node, mod_ctx),
                resolve_type(psi.right, node, mod_ctx),
            )


def check_in_scope(x: Var, node: ast.AST, mod_ctx: ModuleContext) -> None:
    if not isinstance(mod_ctx.gamma.get(x), PredefinedName):
        raise IllFormedModule(node, reasons.NotPredefinedName(x))


def check_body(
    body: list[ast.stmt], mod_ctx: ModuleContext, returns: Type | None = None
) -> StaticOutcome:
    return check_seq(statements(body), mod_ctx, returns)


def check_top_seq(ts: list[Statement], mod_ctx: ModuleContext) -> ModuleContext:
    if len(ts) == 0:
        return mod_ctx
    t, t_ = ts[0], ts[1:]
    r, Sigma = check_top_statement(t, mod_ctx)
    assert isinstance(r, Assigns), "top-level return rejected by check_stmt"
    delta = r.delta
    mod_ctx_after = override_gamma(replace(mod_ctx, Sigma=Sigma), delta)
    if len(t_) == 0:
        return mod_ctx_after
    return check_top_seq(t_, mod_ctx_after)


def check_top_statement(t: Statement, mod_ctx: ModuleContext) -> tuple[StaticOutcome, ClassTable]:
    if isinstance(t, ast.ClassDef):
        c, Sigma = class_declared(t, mod_ctx)
        return Assigns({t.name: c}), Sigma
    return check_statement(t, mod_ctx, None), mod_ctx.Sigma


def check_seq(
    ss: list[Statement], mod_ctx: ModuleContext, returns: Type | None = None
) -> StaticOutcome:
    if len(ss) == 0:
        return Assigns({})
    s, s_ = ss[0], ss[1:]
    r = check_statement(s, mod_ctx, returns)
    if len(s_) == 0:
        return r
    if isinstance(r, Returns):
        stmt: ast.AST = s_[0][0] if isinstance(s_[0], list) else s_[0]
        raise IllFormedModule(stmt, reasons.UnreachableStatement())
    r_ = check_seq(s_, override_gamma(mod_ctx, r.delta), returns)
    return override_outcomes(r, r_)


def check_statement(s: Statement, mod_ctx: ModuleContext, returns: Type | None) -> StaticOutcome:
    if isinstance(s, list):
        check_mutual_region(s, mod_ctx)
        return Assigns({d.name: signature(d, mod_ctx) for d in s})
    return check_stmt(s, mod_ctx, returns)


def check_mutual_region(defs: list[ast.FunctionDef], mod_ctx: ModuleContext) -> None:
    for d in defs:
        if mod_ctx.gamma.get(d.name) != Unbound():
            raise IllFormedModule(d, reasons.Redeclaration(d.name))
    check_bodies(defs, mod_ctx)


def check_bodies(defs: list[ast.FunctionDef], mod_ctx: ModuleContext) -> None:
    f_names: VarContext = {d.name: signature(d, mod_ctx) for d in defs}
    for d in defs:
        check_distinct_declarations(d.body)
        params = parameters(d, mod_ctx)
        check_assignments_declared(d.body, set(params))
        locals_ = assigns_body(d.body) - set(params)
        delta = {**f_names, **params, **{x: Unbound() for x in locals_}}
        body_ctx = override_gamma(mod_ctx, delta)
        declared = resolve_type(type_expr(d.returns), d, mod_ctx)
        r = check_body(d.body, body_ctx, declared)
        if not isinstance(r, Returns):
            check_implicit_return(mod_ctx.Sigma, d, declared)


def check_implicit_return(Sigma: ClassTable, d: ast.FunctionDef, declared: Type) -> None:
    if not subtype(Sigma, Primitive.NONE, declared):
        raise IllFormedModule(d, reasons.MissingReturn(d.name, declared))


def check_returns_none(Sigma: ClassTable, s: ast.Return, declared: Type) -> None:
    if not subtype(Sigma, Primitive.NONE, declared):
        raise IllFormedModule(s, reasons.TypeMismatch(declared, Primitive.NONE))


def check_distinct_declarations(body: list[ast.stmt]) -> None:
    repeated = redeclaration(body)
    if repeated is not None:
        x, node = repeated
        raise IllFormedModule(node, reasons.Redeclaration(x))


def check_assignments_declared(body: list[ast.stmt], bound: set[Var]) -> None:
    """Diagnostics for assignments the rules reject as unbound: a target never declared in the
    scope, other than a parameter or pattern variable, or one declared only later in the text."""
    first_declaration: dict[Var, ast.stmt] = {}
    for x, node in reversed(declares_body(body)):
        first_declaration[x] = node
    for x, node in assign_targets(body):
        if x not in first_declaration:
            if x not in bound and x not in pattern_bound(body):
                raise IllFormedModule(node, reasons.UndeclaredAssignment(x))
        elif position(first_declaration[x]) > position(node):
            raise IllFormedModule(node, reasons.AssignmentBeforeDeclaration(x))


def position(node: ast.stmt) -> tuple[int, int]:
    return (node.lineno, node.col_offset)


def check_declarable(x: Var, node: ast.AST, mod_ctx: ModuleContext) -> None:
    if mod_ctx.gamma.get(x) != Unbound():
        raise IllFormedModule(node, reasons.Redeclaration(x))


def check_stmt(s: ast.stmt, mod_ctx: ModuleContext, returns: Type | None) -> StaticOutcome:
    match s:
        case ast.Pass():
            return Assigns({})
        case ast.Assign():
            (target,) = s.targets
            assert isinstance(target, ast.Name)
            x = target.id
            match mod_ctx.gamma.get(x):
                case DeclTy(tau):
                    check_expr(s.value, tau, mod_ctx)
                    return Assigns({x: tau})
                case Unbound():
                    raise IllFormedModule(s, reasons.MaybeAssigned(x))
                case Class() | ModuleStub() | ModuleLoaded() | PredefinedName():
                    raise IllFormedModule(s, reasons.Redeclaration(x))
                case _:
                    assert x in mod_ctx.gamma, (
                        "name assigned in scope pre-populated by def or module"
                    )
                    raise IllFormedModule(s, reasons.Reassignment(x))
        case ast.AnnAssign():
            assert isinstance(s.target, ast.Name)
            x = s.target.id
            check_declarable(x, s, mod_ctx)
            tau = resolve_type(type_expr(s.annotation), s, mod_ctx)
            if s.value is None:
                return Assigns({x: DeclTy(tau)})
            check_expr(s.value, tau, mod_ctx)
            return Assigns({x: tau})
        case ast.Expr(value=e):
            synth_expr(e, mod_ctx)
            return Assigns({})
        case ast.Return(value=e):
            if returns is None:  # no return rule with empty return type
                raise IllFormedModule(s, reasons.TopLevelReturn())
            if e is None:
                check_returns_none(mod_ctx.Sigma, s, returns)
            else:
                check_expr(e, returns, mod_ctx)
            return Returns()
        case ast.If(test=e, body=ss, orelse=ss_):
            check_expr(e, Primitive.BOOL, mod_ctx)
            branches = [check_body(ss, mod_ctx, returns)]
            branches.append(check_body(ss_, mod_ctx, returns) if ss_ else Assigns({}))
            return merge_outcomes(branches)
        case ast.Assert(test=e, msg=e_):
            check_expr(e, Primitive.BOOL, mod_ctx)
            if e_ is not None:
                check_expr(e_, Primitive.STR, mod_ctx)
            return Assigns({})
        case ast.Match(subject=e, cases=cases):
            tau = synth_expr(e, mod_ctx)
            return check_match_cases(cases, tau, mod_ctx, returns)
        case _:
            raise AssertionError(f"unexpected statement: {type(s).__name__}")


def check_match_cases(
    cases: list[ast.match_case],
    tau: Type,
    mod_ctx: ModuleContext,
    returns: Type | None,
) -> StaticOutcome:
    deltas, partial = match_cases(cases, tau, mod_ctx)
    branches = [check_case(case, delta, mod_ctx, returns) for case, delta in zip(cases, deltas)]
    return merge_outcomes(branches + ([Assigns({})] if partial else []))


def match_cases(
    cases: list[ast.match_case], tau: Type, mod_ctx: ModuleContext
) -> tuple[list[VarContext], bool]:
    residual = shapes(mod_ctx.Sigma, tau, frozenset())
    deltas: list[VarContext] = []
    for index, case in enumerate(cases, 1):
        mismatch = seq_safe(case.pattern, tau, mod_ctx)
        if mismatch is not None:
            q, sigma = mismatch
            kind = "list" if isinstance(q, PatList) else "tuple"
            raise IllFormedModule(q, reasons.SequenceKindMismatch(kind, sigma))
        result = match_shapes(residual, case.pattern, mod_ctx)
        if result is None:
            raise IllFormedModule(case.pattern, reasons.UnreachableCase(index))
        _, residual, delta = result
        deltas.append(delta)
    return deltas, len(residual) > 0


def check_case(
    case: ast.match_case,
    delta: VarContext,
    mod_ctx: ModuleContext,
    returns: Type | None,
) -> StaticOutcome:
    return override_outcomes(
        Assigns(delta), check_body(case.body, override_gamma(mod_ctx, delta), returns)
    )


def synth_expr(e: ast.expr, mod_ctx: ModuleContext) -> Type:
    match e:
        case ast.Name(id=x):
            if not is_assigned(mod_ctx, x):
                if module_of(mod_ctx, x) is not None:
                    raise IllFormedModule(e, reasons.ModuleAsValue(QualifiedName((x,))))
                theta = mod_ctx.gamma.get(x)
                match theta:
                    case Class():
                        raise IllFormedModule(e, reasons.ClassAsValue(QualifiedName((x,))))
                    case PredefinedName():
                        raise IllFormedModule(e, reasons.PredefinedNameAsValue(QualifiedName((x,))))
                    case Unbound():
                        raise IllFormedModule(e, reasons.UnboundName(x))
                    case DeclTy():
                        raise IllFormedModule(e, reasons.UnassignedVariable(x))
                    case _:
                        raise IllFormedModule(e, reasons.UndefinedVariable(x))
            tau = assigned_type(mod_ctx, x)
            assert tau is not None
            return tau
        case ast.Constant():
            return LiteralType(e.value)
        case ast.Lambda():
            raise IllFormedModule(e, reasons.NotSynthesised())
        case ast.Call():
            c = class_of_name(e.func, mod_ctx)
            return call(e, mod_ctx) if c is None else constr(c, e, mod_ctx)
        case ast.BinOp():
            return binary(BINARY_NAMES[type(e.op)], e.left, e.right, e, mod_ctx)
        case ast.UnaryOp():
            operand = synth_expr(e.operand, mod_ctx)
            negated = literal_type(e)
            if negated is not None:
                return negated
            name = UNARY_NAMES[type(e.op)]
            resolved = minimum(mod_ctx.Sigma, overloads_unary(mod_ctx.Sigma, name, operand))
            if resolved is None:
                raise IllFormedModule(e, reasons.NoUnaryOverload(name, operand))
            _, result = resolved
            return result
        case ast.BoolOp(values=es):
            for v in es:
                check_expr(v, Primitive.BOOL, mod_ctx)
            return Primitive.BOOL
        case ast.Compare():
            assert len(e.ops) == 1
            return binary(BINARY_NAMES[type(e.ops[0])], e.left, e.comparators[0], e, mod_ctx)
        case ast.IfExp(test=e_):
            check_expr(e_, Primitive.BOOL, mod_ctx)
            return branch_type(e, mod_ctx)
        case ast.Attribute(value=e_, attr=x):
            parent = entry_of(e_, mod_ctx)
            match parent:
                case ModuleLoaded():
                    return attr_module(parent, x, e)
                case ModuleStub(q):
                    raise IllFormedModule(e, reasons.SubmoduleNotImported(q))
                case _:
                    return attribute_type(synth_expr(e_, mod_ctx), e, mod_ctx)
        case ast.Subscript(value=e_):
            return subscript_type(synth_expr(e_, mod_ctx), e, mod_ctx)
        case ast.Tuple(elts=es):
            return TupleType(tuple(synth_expr(e_, mod_ctx) for e_ in es))
        case ast.List(elts=es):
            return list_type(e, es, mod_ctx)
        case ast.Dict(values=es):
            for k in dict_keys(e):
                check_expr(k, Primitive.STR, mod_ctx)
            return dict_type(e, es, mod_ctx)
        case ast.ListComp(elt=e_, generators=gs):
            return ListType(base_type(synth_expr(e_, qual_context([e_], gs, mod_ctx))))
        case ast.DictComp():
            mod_ctx_ = qual_context([e.key, e.value], e.generators, mod_ctx)
            check_expr(e.key, Primitive.STR, mod_ctx_)
            return DictType(base_type(synth_expr(e.value, mod_ctx_)))
        case _:
            raise AssertionError(f"unexpected expression: {type(e).__name__}")


def attr_module(parent: ModuleLoaded, x: Var, e: ast.Attribute) -> Type:
    theta = parent.members.get(x)
    match theta:
        case None:
            raise IllFormedModule(e, reasons.UnknownMember(x, parent.q))
        case ModuleStub(q):
            raise IllFormedModule(e, reasons.SubmoduleNotImported(q))
        case ModuleLoaded():
            raise IllFormedModule(e, reasons.ModuleAsValue(qualified_name(e)))
        case Class():
            raise IllFormedModule(e, reasons.ClassAsValue(qualified_name(e)))
        case PredefinedName():
            raise IllFormedModule(e, reasons.PredefinedNameAsValue(qualified_name(e)))
        case Unbound():
            raise IllFormedModule(e, reasons.UnassignedMember(x, parent.q))
        case DeclTy():
            raise IllFormedModule(e, reasons.UnassignedMember(x, parent.q))
        case _:
            return theta


def attribute_type(obj: Type, e: ast.Attribute, mod_ctx: ModuleContext) -> Type:
    match obj:
        case UnionType(sigma, tau):
            return join_seq(
                mod_ctx.Sigma,
                [attribute_type(sigma, e, mod_ctx), attribute_type(tau, e, mod_ctx)],
            )
        case ClassType(c):
            member = field_type(mod_ctx.Sigma, c, e.attr)
            if member is None:
                raise IllFormedModule(e, reasons.UnknownField(short_name(c), e.attr))
            return member
        case _:
            raise IllFormedModule(e, reasons.NoAttributes(obj))


def subscript_type(container: Type, e: ast.Subscript, mod_ctx: ModuleContext) -> Type:
    if container == Primitive.STR:
        check_expr(e.slice, Primitive.INT, mod_ctx)
        return Primitive.STR
    match container:
        case UnionType(sigma, tau):
            return join_seq(
                mod_ctx.Sigma,
                [subscript_type(sigma, e, mod_ctx), subscript_type(tau, e, mod_ctx)],
            )
        case ListType(tau):
            check_expr(e.slice, Primitive.INT, mod_ctx)
            return tau
        case DictType(tau):
            check_expr(e.slice, Primitive.STR, mod_ctx)
            return tau
        case TupleType():
            return tuple_subscript_type(container, e.slice, mod_ctx)
        case _:
            raise IllFormedModule(e, reasons.NotSubscriptable(container))


def tuple_subscript_type(container: TupleType, index: ast.expr, mod_ctx: ModuleContext) -> Type:
    m = len(container.components)
    actual = synth_expr(index, mod_ctx)
    i = literal_index(actual)
    if i is None:
        if actual != Primitive.INT:
            raise IllFormedModule(index, reasons.TypeMismatch(Primitive.INT, actual))
        return join_seq(mod_ctx.Sigma, container.components)
    if not -m <= i < m:
        raise IllFormedModule(index, reasons.TupleIndexOutOfRange(i, m))
    return container.components[i]


def literal_index(tau: Type) -> int | None:
    if not isinstance(tau, LiteralType):
        return None
    v = tau.value
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def branch_type(e: ast.IfExp, mod_ctx: ModuleContext) -> Type:
    branches = [e.body, e.orelse]
    taus = [synth_expr(branch, mod_ctx) for branch in branches if synthesises(branch)]
    if len(taus) == 0:
        raise IllFormedModule(e, reasons.NotSynthesised())
    tau = join_seq(mod_ctx.Sigma, taus)
    for branch in branches:
        if not synthesises(branch):
            check_expr(branch, tau, mod_ctx)
    return tau


def list_type(node: ast.expr, es: list[ast.expr], mod_ctx: ModuleContext) -> ListType:
    taus = [base_type(synth_expr(e, mod_ctx)) for e in es if synthesises(e)]
    if len(taus) == 0:
        raise IllFormedModule(node, reasons.NotSynthesised())
    tau = join_seq(mod_ctx.Sigma, taus)
    for e in es:
        if not synthesises(e):
            check_expr(e, tau, mod_ctx)
    return ListType(tau)


def synthesises(e: ast.expr) -> bool:
    match e:
        case ast.Lambda():
            return False
        case ast.IfExp():
            return synthesises(e.body) or synthesises(e.orelse)
        case ast.List(elts=es):
            return any(synthesises(e_) for e_ in es)
        case ast.Dict(values=es):
            return any(synthesises(v) for v in es)
        case ast.Tuple(elts=es):
            return all(synthesises(e_) for e_ in es)
        case ast.ListComp(elt=e_):
            return synthesises(e_)
        case ast.DictComp(value=e_):
            return synthesises(e_)
        case ast.Call(func=ast.Lambda(body=e_), args=es):
            return synthesises(e_) and all(synthesises(a) for a in es)
        case _:
            return True


def dict_type(node: ast.expr, es: list[ast.expr], mod_ctx: ModuleContext) -> DictType:
    return DictType(list_type(node, es, mod_ctx).elem)


def constr(c: Class, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    xs = fields(mod_ctx.Sigma, c)
    kwd_names = [k.arg for k in e.keywords if k.arg is not None]
    args = field_map(mod_ctx.Sigma, c, e.args, kwd_names, [k.value for k in e.keywords])
    if args is None:
        n = len(e.args)
        if n + len(kwd_names) != len(xs):
            raise IllFormedModule(
                e, reasons.ConstructorArityMismatch(short_name(c), len(xs), n + len(kwd_names))
            )
        raise IllFormedModule(
            e, reasons.UnknownConstructorKeyword(short_name(c), tuple(sorted(set(xs[n:]))))
        )
    for x, arg in args.items():
        check_expr(arg, declared_type(mod_ctx.Sigma, c, x), mod_ctx)
    return ClassType(c)


def call(e: ast.Call, mod_ctx: ModuleContext) -> Type:
    if isinstance(e.func, ast.Lambda):
        return applied_lambda(e.func, e, mod_ctx)
    return result_type(synth_expr(e.func, mod_ctx), e, mod_ctx)


def result_type(fn: Type, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    match fn:
        case UnionType(sigma, tau):
            return join_seq(
                mod_ctx.Sigma,
                [result_type(sigma, e, mod_ctx), result_type(tau, e, mod_ctx)],
            )
        case CallableType(sigmas, tau):
            if len(sigmas) != len(e.args):
                raise IllFormedModule(e, reasons.CallArityMismatch(len(sigmas), len(e.args)))
            for arg, param in zip(e.args, sigmas):
                check_expr(arg, param, mod_ctx)
            return tau
        case _:
            raise IllFormedModule(e, reasons.NotCallable(fn))


def applied_lambda(f: ast.Lambda, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    return synth_expr(f.body, override_gamma(mod_ctx, lambda_arguments(f, e, mod_ctx)))


def lambda_arguments(f: ast.Lambda, e: ast.Call, mod_ctx: ModuleContext) -> VarContext:
    params = [a.arg for a in f.args.args]
    if len(params) != len(e.args):
        raise IllFormedModule(e, reasons.CallArityMismatch(len(params), len(e.args)))
    return {x: synth_expr(arg, mod_ctx) for x, arg in zip(params, e.args)}


def check_expr(e: ast.expr, expected: Type, mod_ctx: ModuleContext) -> None:
    match e, expected:
        case ast.Call(func=ast.Lambda() as f), _:
            check_expr(
                f.body,
                expected,
                override_gamma(mod_ctx, lambda_arguments(f, e, mod_ctx)),
            )
            return
        case ast.List(elts=es), ListType(tau):
            for e_ in es:
                check_expr(e_, tau, mod_ctx)
            return
        case ast.Tuple(elts=es), TupleType(taus):
            if len(es) == len(taus):
                for x, t in zip(es, taus):
                    check_expr(x, t, mod_ctx)
                return
        case ast.Dict(values=es), DictType(tau):
            for k in dict_keys(e):
                check_expr(k, Primitive.STR, mod_ctx)
            for v in es:
                check_expr(v, tau, mod_ctx)
            return
        case ast.Lambda(), _:
            check_lambda(e, expected, mod_ctx)
            return
        case ast.IfExp(), _:
            check_expr(e.test, Primitive.BOOL, mod_ctx)
            check_expr(e.body, expected, mod_ctx)
            check_expr(e.orelse, expected, mod_ctx)
            return
        case ast.ListComp(elt=e_, generators=gs), ListType(tau):
            check_expr(e_, tau, qual_context([e_], gs, mod_ctx))
            return
        case ast.DictComp(), DictType(tau):
            mod_ctx_ = qual_context([e.key, e.value], e.generators, mod_ctx)
            check_expr(e.key, Primitive.STR, mod_ctx_)
            check_expr(e.value, tau, mod_ctx_)
            return
    actual = synth_expr(e, mod_ctx)
    if not subtype(mod_ctx.Sigma, actual, expected):
        raise IllFormedModule(e, reasons.TypeMismatch(expected, actual))


def check_lambda(e: ast.Lambda, expected: Type, mod_ctx: ModuleContext) -> None:
    params = [a.arg for a in e.args.args]
    if not isinstance(expected, CallableType):
        raise IllFormedModule(e, reasons.LambdaTypeMismatch(expected, None))
    if len(params) != len(expected.params):
        raise IllFormedModule(
            e,
            reasons.LambdaTypeMismatch(expected, len(params)),
        )
    delta = dict(zip(params, expected.params))
    check_expr(e.body, expected.result, override_gamma(mod_ctx, delta))


def binary(op: str, left: ast.expr, right: ast.expr, e: ast.expr, mod_ctx: ModuleContext) -> Type:
    sigma, sigma_ = synth_expr(left, mod_ctx), synth_expr(right, mod_ctx)
    resolved = minimum(mod_ctx.Sigma, overloads_binary(mod_ctx.Sigma, op, sigma, sigma_))
    if resolved is None:
        raise IllFormedModule(e, reasons.NoBinaryOverload(op, sigma, sigma_))
    _, result = resolved
    return result


def qual_context(
    elts: list[ast.expr], generators: list[ast.comprehension], mod_ctx: ModuleContext
) -> ModuleContext:
    delta = check_quals(generators, mod_ctx)
    captured = captures_e_list(elts) & binds_quals(generators)
    if len(captured) > 0:
        node = generators[0].target
        raise IllFormedModule(node, reasons.CapturedGeneratorVariable(min(captured)))
    return override_gamma(mod_ctx, delta)


def check_quals(generators: list[ast.comprehension], mod_ctx: ModuleContext) -> VarContext:
    if len(generators) == 0:
        return {}
    g = generators[0]
    tau = iterated_type(g.iter, mod_ctx)
    x = target_name(g)
    if x in captures_e_list(g.ifs) | captures_quals(generators[1:]):
        raise IllFormedModule(g.target, reasons.CapturedGeneratorVariable(x))
    delta = {x: tau}
    mod_ctx_ = override_gamma(mod_ctx, delta)
    for e in g.ifs:
        check_expr(e, Primitive.BOOL, mod_ctx_)
    return {**delta, **check_quals(generators[1:], mod_ctx_)}


def elem_type(Sigma: ClassTable, tau: Type) -> Type | None:
    if tau == Primitive.STR:
        return Primitive.STR
    match tau:
        case ListType(sigma):
            return sigma
        case DictType():
            return Primitive.STR
        case TupleType(taus):
            return join_seq(Sigma, [base_type(c) for c in taus])
        case UnionType(sigma, sigma_):
            left, right = elem_type(Sigma, sigma), elem_type(Sigma, sigma_)
            return None if left is None or right is None else join_seq(Sigma, [left, right])
        case _:
            return None


def iterated_type(e: ast.expr, mod_ctx: ModuleContext) -> Type:
    t = synth_expr(e, mod_ctx)
    elem = elem_type(mod_ctx.Sigma, t)
    if elem is None:
        raise IllFormedModule(e, reasons.NotIterable(t))
    return elem


def class_declared(node: ast.ClassDef, mod_ctx: ModuleContext) -> tuple[Class, ClassTable]:
    check_declarable(node.name, node, mod_ctx)
    if not isinstance(mod_ctx.gamma.get("dataclass"), PredefinedName):
        raise IllFormedModule(node, reasons.NotPredefinedName("dataclass"))
    own = tuple((x, resolve_type(psi, node, mod_ctx)) for x, psi in own_fields(node))
    names = [x for x, _ in own]
    dup = next((n for i, n in enumerate(names) if n in names[:i]), None)
    if dup is not None:
        raise IllFormedModule(node, reasons.DuplicateField(dup, node.name))
    base: Class | None = None
    if len(node.bases) > 0:
        assert isinstance(node.bases[0], ast.Name)
        base_name = node.bases[0].id
        theta = mod_ctx.gamma.get(base_name)
        if not isinstance(theta, Class):
            raise IllFormedModule(node, reasons.NotClass(QualifiedName((base_name,))))
        base = theta
        duplicates = set(names) & set(fields(mod_ctx.Sigma, base))
        if len(duplicates) > 0:
            raise IllFormedModule(node, reasons.DuplicateField(min(duplicates), node.name))
    c = Class(qualified(mod_ctx.q, node.name))
    assert c not in mod_ctx.Sigma, "redeclaration rejected by class rule"
    return c, {**mod_ctx.Sigma, c: ClassTableEntry(own_fields=own, base=base)}
