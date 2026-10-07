import ast
from collections.abc import Sequence
from dataclasses import replace
from functools import reduce
from typing import cast

import reasons
from aux import (
    Statement,
    TypeDeclaration,
    assign_targets,
    assigns_body,
    binds_quals,
    captures_list,
    captures_quals,
    declares,
    declares_body,
    dict_keys,
    name_of,
    own_fields,
    pattern_bound,
    statements,
    target_name,
    type_expr,
    type_param_names,
)
from classes import (
    ArityMismatch,
    ClassTable,
    RepeatedKeywordArg,
    UnknownKeywordArgs,
    class_table,
    declared_type,
    field_map,
    field_names,
    field_type,
    fields,
    no_field_map,
    resolve_type,
    short_name,
)
from contexts import (
    DU,
    PU,
    Assigns,
    Context,
    ModuleChecked,
    ModuleContext,
    ModuleStub,
    PredefinedName,
    Returns,
    StaticOutcome,
    TypeAlias,
    TypeScheme,
    TypeVar,
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
    type_context,
    type_entry,
)
from match import check_pattern, match_shapes, remaining
from operators import (
    BINARY_NAMES,
    UNARY_NAMES,
    resolve_op_binary,
    resolve_op_unary,
)
from reasons import IllFormedModule, MypyCompatibility
from shapes import Shapes, shapes
from subtyping import equivalent, join_seq, subtype, type_args_seq
from syntax import render_pattern
from type_syntax import (
    RANGE,
    CallableType,
    Class,
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Name,
    Primitive,
    TupleType,
    Type,
    TypeName,
    TypeVariable,
    UnionType,
    Var,
    base_type,
    literal_type,
    parse_annotation,
    substitute,
)


def def_signature(d: ast.FunctionDef, mod_ctx: ModuleContext) -> CallableType | TypeScheme:
    alphas = type_param_names(d)
    mod_ctx_ = override_gamma(mod_ctx, {alpha: TypeVar() for alpha in alphas})
    tau = CallableType(
        tuple(resolve_type(type_expr(a.annotation), a, mod_ctx_) for a in d.args.args),
        resolve_type(type_expr(d.returns), d, mod_ctx_),
    )
    return tau if len(alphas) == 0 else TypeScheme(alphas, tau)


# tail: the body ends a function body, so a fall-through is a missing return
def check_body(
    body: list[ast.stmt], mod_ctx: ModuleContext, returns: Type | None = None, tail: bool = False
) -> StaticOutcome:
    return check_seq(statements(body), mod_ctx, returns, tail)


def check_top_seq(ts: list[Statement], mod_ctx: ModuleContext) -> ModuleContext:
    if len(ts) == 0:
        return mod_ctx
    t, t_ = ts[0], ts[1:]
    r, Sigma = check_top_statement(t, mod_ctx)
    assert isinstance(r, Assigns)
    delta = r.delta
    mod_ctx_after = override_gamma(replace(mod_ctx, Sigma=Sigma), delta)
    if len(t_) == 0:
        return mod_ctx_after
    return check_top_seq(t_, mod_ctx_after)


def check_top_statement(t: Statement, mod_ctx: ModuleContext) -> tuple[StaticOutcome, ClassTable]:
    if isinstance(t, list) and isinstance(t[0], (ast.ClassDef, ast.TypeAlias)):
        return types(t, mod_ctx)
    return check_statement(t, mod_ctx, None), mod_ctx.Sigma


def types(xis: list[TypeDeclaration], mod_ctx: ModuleContext) -> tuple[StaticOutcome, ClassTable]:
    xis_ = tuple(xis)
    gamma, q = mod_ctx.gamma, mod_ctx.q
    deltas = [
        {x: type_entry(gamma, q, xis_, i) for x, _ in declares(xi)} for i, xi in enumerate(xis_)
    ]
    Sigma = reduce(
        lambda Sigma, i: {**Sigma, **class_table(gamma, q, xis_, i)},
        range(len(xis_)),
        mod_ctx.Sigma,
    )
    for i, xi in enumerate(xis_):
        declaration(
            xi, ModuleContext(gamma=type_context(gamma, q, xis_, i), M=mod_ctx.M, q=q, Sigma=Sigma)
        )
    return Assigns({x: theta for delta in deltas for x, theta in delta.items()}), Sigma


def declaration(xi: TypeDeclaration, mod_ctx: ModuleContext) -> None:
    if isinstance(xi, ast.ClassDef):
        dataclass(xi, mod_ctx)
    else:
        type_alias(xi, mod_ctx)


def check_seq(
    ss: list[Statement], mod_ctx: ModuleContext, returns: Type | None = None, tail: bool = False
) -> StaticOutcome:
    if len(ss) == 0:
        return Assigns({})
    s, s_ = ss[0], ss[1:]
    r = check_statement(s, mod_ctx, returns, tail and len(s_) == 0)
    if len(s_) == 0:
        return r
    if isinstance(r, Returns):
        stmt: ast.AST = s_[0][0] if isinstance(s_[0], list) else s_[0]
        raise IllFormedModule(stmt, reasons.UnreachableStatement())
    r_ = check_seq(s_, override_gamma(mod_ctx, r.delta), returns, tail)
    return override_outcomes(r, r_)


def check_statement(
    s: Statement, mod_ctx: ModuleContext, returns: Type | None, tail: bool = False
) -> StaticOutcome:
    if isinstance(s, list):
        return check_defs(cast(list[ast.FunctionDef], s), mod_ctx)
    return check_stmt(s, mod_ctx, returns, tail)


def check_defs(ds: list[ast.FunctionDef], mod_ctx: ModuleContext) -> Assigns:
    pis = {d.name: def_signature(d, mod_ctx) for d in ds}
    delta: Context = dict(pis)
    for d in ds:
        def_body(d, pis[d.name], override_gamma(mod_ctx, delta))
    return Assigns(delta)


def def_body(d: ast.FunctionDef, pi: CallableType | TypeScheme, mod_ctx: ModuleContext) -> None:
    alphas, tau = (pi.params, pi.tau) if isinstance(pi, TypeScheme) else ((), pi)
    assert isinstance(tau, CallableType)
    xs = parameter_names(d.args, d, d.name)
    check_assignments_declared(d.body, set(xs))
    params = dict(zip(xs, tau.params, strict=True))
    type_vars = {alpha: TypeVar() for alpha in alphas}
    body_ctx = override_gamma(mod_ctx, {**type_vars, **params, **scope(set(xs), d.body)})
    r = check_body(d.body, body_ctx, tau.result, tail=True)
    if not isinstance(r, Returns) and not equivalent(mod_ctx.Sigma, tau.result, Primitive.NONE):
        raise mypy_only_if(subtype(mod_ctx.Sigma, Primitive.NONE, tau.result))(
            d, reasons.MissingReturn(d.name, tau.result)
        )


def parameter_names(args: ast.arguments, node: ast.AST, f: Var | None) -> list[Var]:
    xs = [a.arg for a in args.args]
    dup = next((x for i, x in enumerate(xs) if x in xs[:i]), None)
    if dup is not None:
        raise IllFormedModule(node, reasons.DuplicateParameter(dup, f))
    return xs


def check_returns_none(Sigma: ClassTable, s: ast.Return, declared: Type) -> None:
    if not equivalent(Sigma, declared, Primitive.NONE):
        raise mypy_only_if(subtype(Sigma, Primitive.NONE, declared))(
            s, reasons.BareReturn(declared)
        )


# Failure is for mypy compatibility only when the program is otherwise well-formed.
def mypy_only_if(otherwise_well_formed: bool) -> type[IllFormedModule]:
    return MypyCompatibility if otherwise_well_formed else IllFormedModule


def scope(ys: set[Var], body: list[ast.stmt]) -> VarContext:
    patterns = pattern_bound(body)
    seen = set(ys)
    for x, node in declares_body(body):
        if x in seen or x in patterns:
            raise IllFormedModule(node, reasons.Redeclaration(x))
        seen.add(x)
    for x in sorted(ys & patterns.keys()):
        raise IllFormedModule(patterns[x], reasons.Redeclaration(x))
    return {x: Unbound() for x in assigns_body(body) if x not in ys}


def check_assignments_declared(body: list[ast.stmt], bound: set[Var]) -> None:
    """Diagnostic for an assignment the rules reject as unbound: a target never declared in the
    scope, other than a parameter or pattern variable."""
    declared = {x for x, _ in declares_body(body)}
    for x, node in assign_targets(body):
        if x not in declared and x not in bound and x not in pattern_bound(body):
            raise IllFormedModule(node, reasons.UndeclaredAssignment(x))


def check_stmt(
    s: ast.stmt, mod_ctx: ModuleContext, returns: Type | None, tail: bool = False
) -> StaticOutcome:
    match s:
        case ast.Pass():
            return Assigns({})
        case ast.Assign():
            (target,) = s.targets
            assert isinstance(target, ast.Name)
            x = target.id
            match mod_ctx.gamma.get(x):
                case DU(tau):
                    check_expr(s.value, tau, mod_ctx)
                    return Assigns({x: tau})
                case PU():
                    raise IllFormedModule(s, reasons.MaybeAssigned(x))
                case Unbound():
                    raise IllFormedModule(s, reasons.AssignmentBeforeDeclaration(x))
                case (
                    Class()
                    | ModuleStub()
                    | ModuleChecked()
                    | PredefinedName()
                    | TypeVar()
                    | TypeAlias()
                ):
                    raise IllFormedModule(s, reasons.Redeclaration(x))
                case _:
                    assert x in mod_ctx.gamma
                    raise IllFormedModule(s, reasons.Reassignment(x))
        case ast.AnnAssign():
            assert isinstance(s.target, ast.Name)
            x = s.target.id
            tau = resolve_type(type_expr(s.annotation), s, mod_ctx)
            if s.value is None:
                return Assigns({x: DU(tau)})
            check_expr(s.value, tau, mod_ctx)
            return Assigns({x: tau})
        case ast.Expr(value=ast.Call(func=f) as e) if not isinstance(f, ast.Lambda) and (
            class_of_name(f, mod_ctx) is None
        ):
            call_stmt(e, mod_ctx)
            return Assigns({})
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
            branches = [check_body(ss, mod_ctx, returns, tail)]
            branches.append(check_body(ss_, mod_ctx, returns, tail) if ss_ else Assigns({}))
            return merge_outcomes(branches, {x for x, _ in declares(s)})
        case ast.Assert(test=e, msg=e_):
            check_expr(e, Primitive.BOOL, mod_ctx)
            if e_ is not None:
                check_expr(e_, Primitive.STR, mod_ctx)
            return Assigns({})
        case ast.Match(subject=e):
            tau = synth_expr(e, mod_ctx)
            return check_match_cases(s, tau, mod_ctx, returns, tail)
        case _:
            raise AssertionError(f"unexpected statement: {type(s).__name__}")


def check_match_cases(
    match: ast.Match, tau: Type, mod_ctx: ModuleContext, returns: Type | None, tail: bool
) -> StaticOutcome:
    deltas, rest, residual = match_cases(match, tau, mod_ctx)
    branches = [
        check_case(case, delta, mod_ctx, returns, tail) for case, delta in zip(match.cases, deltas)
    ]
    partial = rest != Primitive.NEVER
    if (
        partial
        and tail
        and returns is not None
        and not equivalent(mod_ctx.Sigma, returns, Primitive.NONE)
        and len(residual) == 0
        and all(isinstance(r, Returns) for r in branches)
    ):
        raise MypyCompatibility(match, reasons.MissingReturnMatchPartial(rest))
    return merge_outcomes(
        branches + ([Assigns({})] if partial else []), {x for x, _ in declares(match)}
    )


def match_cases(
    match: ast.Match, tau: Type, mod_ctx: ModuleContext
) -> tuple[list[VarContext], Type, Shapes]:
    residual = shapes(mod_ctx.Sigma, tau, frozenset())
    rest = tau
    deltas: list[VarContext] = []
    for case in match.cases:
        deltas.append(check_pattern(case.pattern, rest, mod_ctx))
        result = match_shapes(residual, case.pattern, mod_ctx)
        if result is None:
            raise IllFormedModule(
                case.pattern, reasons.UnreachableCase(render_pattern(case.pattern))
            )
        _, residual = result
        rest = remaining(rest, case.pattern, mod_ctx)
    if rest == Primitive.NEVER:
        assert len(residual) == 0  # the remaining type is coarser than the residual
    return deltas, rest, residual


def check_case(
    case: ast.match_case,
    delta: VarContext,
    mod_ctx: ModuleContext,
    returns: Type | None,
    tail: bool,
) -> StaticOutcome:
    return override_outcomes(
        Assigns(delta), check_body(case.body, override_gamma(mod_ctx, delta), returns, tail)
    )


def synth_expr(e: ast.expr, mod_ctx: ModuleContext) -> Type:
    match e:
        case ast.Name(id=x):
            if not is_assigned(mod_ctx, x):
                if module_of(mod_ctx, x) is not None:
                    raise IllFormedModule(e, reasons.ModuleAsValue(Name((x,))))
                theta = mod_ctx.gamma.get(x)
                match theta:
                    case Class():
                        raise IllFormedModule(e, reasons.ClassAsValue(Name((x,))))
                    case PredefinedName():
                        raise IllFormedModule(e, reasons.PredefinedNameAsValue(Name((x,))))
                    case TypeVar():
                        raise IllFormedModule(e, reasons.TypeParameterAsValue(x))
                    case TypeAlias():
                        raise IllFormedModule(e, reasons.TypeAliasAsValue(Name((x,))))
                    case TypeScheme():
                        raise IllFormedModule(e, reasons.TypeSchemeAsValue(Name((x,))))
                    case Unbound():
                        raise IllFormedModule(e, reasons.UnboundName(x))
                    case DU():
                        raise IllFormedModule(e, reasons.UnassignedVariable(x))
                    case PU(_, declared_in_branch):
                        raise IllFormedModule(e, reasons.PossiblyUnassigned(x, declared_in_branch))
                    case _:
                        raise IllFormedModule(e, reasons.UndefinedVariable(x))
            tau = assigned_type(mod_ctx, x)
            assert tau is not None
            return tau
        case ast.Constant():
            tau = literal_type(e)
            assert tau is not None
            return tau
        case ast.Lambda():
            raise IllFormedModule(e, reasons.NotSynthesised())
        case ast.Call(func=ast.Subscript(value=e_)) if class_of_name(e_, mod_ctx) is not None:
            return constr_explicit(e, mod_ctx)
        case ast.Call():
            c = class_of_name(e.func, mod_ctx)
            return call(e, mod_ctx) if c is None else constr(c, e, mod_ctx)
        case ast.BinOp():
            return binary(BINARY_NAMES[type(e.op)], e.left, e.right, e, mod_ctx)
        case ast.UnaryOp():
            operand = synth_expr(e.operand, mod_ctx)
            name = UNARY_NAMES[type(e.op)]
            result = resolve_op_unary(mod_ctx.Sigma, name, operand)
            if result is None:
                raise IllFormedModule(e, reasons.NoUnaryOverload(name, operand))
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
                case ModuleChecked():
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


def attr_module(parent: ModuleChecked, x: Var, e: ast.Attribute) -> Type:
    theta = parent.members.get(x)
    match theta:
        case None:
            raise IllFormedModule(e, reasons.UnknownMember(x, parent.q))
        case ModuleStub(q):
            raise IllFormedModule(e, reasons.SubmoduleNotImported(q))
        case ModuleChecked():
            raise IllFormedModule(e, reasons.ModuleAsValue(name_of(e)))
        case Class():
            raise IllFormedModule(e, reasons.ClassAsValue(name_of(e)))
        case PredefinedName():
            raise IllFormedModule(e, reasons.PredefinedNameAsValue(name_of(e)))
        case TypeAlias():
            raise IllFormedModule(e, reasons.TypeAliasAsValue(name_of(e)))
        case TypeScheme():
            raise IllFormedModule(e, reasons.TypeSchemeAsValue(name_of(e)))
        case TypeVar():
            raise AssertionError
        case Unbound() | DU() | PU():
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
        case ClassType(c, _):
            member = field_type(mod_ctx.Sigma, obj, e.attr)
            if member is None:
                raise IllFormedModule(e, reasons.UnknownField(short_name(c), e.attr))
            return member
        case _:
            raise IllFormedModule(e, reasons.NoAttributes(obj))


def subscript_type(container: Type, e: ast.Subscript, mod_ctx: ModuleContext) -> Type:
    if base_type(container) == Primitive.STR:
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
    i = integer_literal(actual)
    if i is None:
        if actual != Primitive.INT:
            raise IllFormedModule(index, reasons.TypeMismatch(Primitive.INT, actual))
        return join_seq(mod_ctx.Sigma, container.components)
    if not -m <= i < m:
        raise IllFormedModule(index, reasons.TupleIndexOutOfRange(i, m))
    return container.components[i]


# Used to choose among the tuple subscript rules.
def integer_literal(tau: Type) -> int | None:
    if not isinstance(tau, LiteralType):
        return None
    v = tau.ell.value
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
        case ast.ListComp(elt=e_) | ast.DictComp(value=e_):
            return synthesises(e_)
        case ast.Call(func=ast.Lambda(body=e_), args=es):
            return synthesises(e_) and all(synthesises(a) for a in es)
        case _:
            return True


def dict_type(node: ast.expr, es: list[ast.expr], mod_ctx: ModuleContext) -> DictType:
    return DictType(list_type(node, es, mod_ctx).elem)


def constr(c: Class, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    args = constructor_args(c, e, mod_ctx)
    pi = fields(mod_ctx.Sigma, c)
    alphas = fresh(pi.type_params)
    sigmas = {x: rename(alphas, pi.type_params, sigma) for x, sigma in pi.fields}
    synthesising = [
        (sigmas[x], synth_expr(arg, mod_ctx)) for x, arg in args.items() if synthesises(arg)
    ]
    gamma = type_args_seq(mod_ctx.Sigma, [s for s, _ in synthesising], [t for _, t in synthesising])
    tau = ClassType(c, tuple(type_arguments(gamma, alphas, e)))
    for x, arg in args.items():
        check_expr(arg, declared_type(mod_ctx.Sigma, tau, x), mod_ctx)
    return tau


def constr_explicit(e: ast.Call, mod_ctx: ModuleContext) -> Type:
    tau = resolve_type(type_expr(e.func), e, mod_ctx)
    assert isinstance(tau, ClassType)
    for x, arg in constructor_args(tau.c, e, mod_ctx).items():
        check_expr(arg, declared_type(mod_ctx.Sigma, tau, x), mod_ctx)
    return tau


def constructor_args(c: Class, e: ast.Call, mod_ctx: ModuleContext) -> dict[Var, ast.expr]:
    """Pair fields with arguments by field-map"""
    kwd_names = [k.arg for k in e.keywords if k.arg is not None]
    args = field_map(mod_ctx.Sigma, c, e.args, kwd_names, [k.value for k in e.keywords])
    if args is None:
        name = short_name(c)
        match no_field_map(mod_ctx.Sigma, c, len(e.args), kwd_names):
            case ArityMismatch(expected, given):
                raise IllFormedModule(e, reasons.ConstructorArityMismatch(name, expected, given))
            case UnknownKeywordArgs(xs):
                raise IllFormedModule(e, reasons.UnknownConstructorKeyword(name, xs))
            case RepeatedKeywordArg():
                raise AssertionError  # a syntax error in Python
    return args


def call(e: ast.Call, mod_ctx: ModuleContext) -> Type:
    if isinstance(e.func, ast.Lambda):
        return applied_lambda(e.func, e, mod_ctx)
    return result_type(callee(e, mod_ctx), e, mod_ctx)


def call_stmt(e: ast.Call, mod_ctx: ModuleContext) -> None:
    match callee(e, mod_ctx):
        case CallableType(sigmas, Primitive.NONE):
            check_args(e, sigmas, mod_ctx)
        case fn:
            result_type(fn, e, mod_ctx)


def callee(e: ast.Call, mod_ctx: ModuleContext) -> Type:
    pi = entry_of(e.func, mod_ctx)
    if not isinstance(pi, TypeScheme):
        return synth_expr(e.func, mod_ctx)
    alphas = fresh(pi.params)
    tau = rename(alphas, pi.params, pi.tau)
    assert isinstance(tau, CallableType)
    synthesising = [
        (sigma, synth_expr(arg, mod_ctx))
        for sigma, arg in zip(tau.params, e.args)
        if synthesises(arg)
    ]
    gamma = type_args_seq(mod_ctx.Sigma, [s for s, _ in synthesising], [t for _, t in synthesising])
    return substitute(type_arguments(gamma, alphas, e), alphas, tau)


def fresh(alphas: Sequence[Var]) -> tuple[Var, ...]:
    """Type parameters renamed to variables distinct from any in scope"""
    return tuple(alpha + "'" for alpha in alphas)


def rename(alphas: Sequence[Var], betas: Sequence[Var], sigma: Type) -> Type:
    return substitute([TypeVariable(alpha) for alpha in alphas], betas, sigma)


def type_arguments(gamma: dict[Var, Type], alphas: Sequence[Var], node: ast.AST) -> list[Type]:
    """Context applied to the sequence of type parameters"""
    missing = next((alpha for alpha in alphas if alpha not in gamma), None)
    if missing is not None:
        raise IllFormedModule(node, reasons.NoTypeArgument(missing.removesuffix("'")))
    return [gamma[alpha] for alpha in alphas]


def var_scheme(pi: TypeScheme, e: ast.expr, expected: Type, mod_ctx: ModuleContext) -> None:
    alphas = fresh(pi.params)
    tau = rename(alphas, pi.params, pi.tau)
    gamma = type_args_seq(mod_ctx.Sigma, [tau], [expected])
    actual = substitute(type_arguments(gamma, alphas, e), alphas, tau)
    if not subtype(mod_ctx.Sigma, actual, expected):
        raise IllFormedModule(e, reasons.TypeMismatch(expected, actual))


def result_type(fn: Type, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    match fn:
        case UnionType(sigma, tau):
            return join_seq(
                mod_ctx.Sigma,
                [result_type(sigma, e, mod_ctx), result_type(tau, e, mod_ctx)],
            )
        case CallableType(sigmas, tau):
            check_args(e, sigmas, mod_ctx)
            if tau == Primitive.NONE:
                raise MypyCompatibility(e, reasons.NoneResult())
            return tau
        case _:
            raise IllFormedModule(e, reasons.NotCallable(fn))


def check_args(e: ast.Call, sigmas: Sequence[Type], mod_ctx: ModuleContext) -> None:
    if len(e.keywords) > 0:
        raise IllFormedModule(e, reasons.KeywordArgumentsNotConstructor())
    if len(sigmas) != len(e.args):
        raise IllFormedModule(e, reasons.CallArityMismatch(len(sigmas), len(e.args)))
    for arg, param in zip(e.args, sigmas):
        check_expr(arg, param, mod_ctx)


def applied_lambda(f: ast.Lambda, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    return synth_expr(f.body, override_gamma(mod_ctx, lambda_arguments(f, e, mod_ctx)))


def lambda_arguments(f: ast.Lambda, e: ast.Call, mod_ctx: ModuleContext) -> VarContext:
    params = parameter_names(f.args, f, None)
    if len(e.keywords) > 0:
        raise IllFormedModule(e, reasons.KeywordArgumentsNotConstructor())
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
        case ast.Name() | ast.Attribute(), _ if isinstance(entry_of(e, mod_ctx), TypeScheme):
            pi = entry_of(e, mod_ctx)
            assert isinstance(pi, TypeScheme)
            var_scheme(pi, e, expected, mod_ctx)
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
    params = parameter_names(e.args, e, None)
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
    result = resolve_op_binary(mod_ctx.Sigma, op, sigma, sigma_)
    if result is None:
        raise IllFormedModule(e, reasons.NoBinaryOverload(op, sigma, sigma_))
    return result


def qual_context(
    elts: list[ast.expr], generators: list[ast.comprehension], mod_ctx: ModuleContext
) -> ModuleContext:
    delta = check_quals(generators, mod_ctx)
    captured = captures_list(elts) & binds_quals(generators)
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
    if x in captures_list(g.ifs) | captures_quals(generators[1:]):
        raise IllFormedModule(g.target, reasons.CapturedGeneratorVariable(x))
    delta = {x: tau}
    mod_ctx_ = override_gamma(mod_ctx, delta)
    for e in g.ifs:
        check_expr(e, Primitive.BOOL, mod_ctx_)
    return {**delta, **check_quals(generators[1:], mod_ctx_)}


def elem_type(Sigma: ClassTable, tau: Type) -> Type | None:
    if base_type(tau) == Primitive.STR:
        return Primitive.STR
    match tau:
        case ListType(sigma):
            return sigma
        case DictType():
            return Primitive.STR
        case ClassType(c, ()) if c == RANGE:
            return Primitive.INT
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


def dataclass(node: ast.ClassDef, mod_ctx: ModuleContext) -> None:
    if not isinstance(mod_ctx.gamma.get("dataclass"), PredefinedName):
        raise IllFormedModule(node, reasons.NotPredefinedName("dataclass"))
    own = tuple((x, resolve_type(psi, node, mod_ctx)) for x, psi in own_fields(node))
    base = None if len(node.bases) == 0 else base_class(node, mod_ctx)
    inherited = () if base is None else field_names(mod_ctx.Sigma, base.c)
    names = inherited + tuple(x for x, _ in own)
    dup = next((x for i, x in enumerate(names) if x in names[:i]), None)
    if dup is not None:
        raise IllFormedModule(node, reasons.DuplicateField(dup, node.name))


def type_alias(node: ast.TypeAlias, mod_ctx: ModuleContext) -> None:
    resolve_type(type_expr(node.value), node, mod_ctx)


def base_class(node: ast.ClassDef, mod_ctx: ModuleContext) -> ClassType:
    psi = parse_annotation(node.bases[0])
    assert isinstance(psi, TypeName)
    if isinstance(resolve_name(psi.q, mod_ctx), TypeAlias):
        raise IllFormedModule(node, reasons.NotClass(psi.q))
    tau = resolve_type(psi, node, mod_ctx)
    if not isinstance(tau, ClassType):
        raise IllFormedModule(node, reasons.NotClass(psi.q))
    return tau
