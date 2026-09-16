import ast
from dataclasses import replace

import reasons
from aux import (
    Statement,
    assigns_body,
    assigns_seq,
    binds_quals,
    captures_e,
    captures_e_list,
    captures_quals,
    captures_statement,
    dict_keys,
    first_assigning_statement,
    own_fields,
    qualified_name,
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
    ModuleContext,
    ModuleLoaded,
    ModuleStub,
    PredefinedName,
    Returns,
    StaticOutcome,
    Status,
    VarContext,
    class_of_name,
    entry_of,
    is_assigned,
    merge_outcomes,
    module_of,
    override_gamma,
    override_outcomes,
    resolve_name,
    var_type,
)
from match import literal_of, match_shapes, seq_safe
from operators import (
    BINARY_NAMES,
    UNARY_NAMES,
    minimum,
    overloads_binary,
    overloads_unary,
)
from reasons import IllFormedModule
from shapes import Shape, shapes
from subtyping import join, subtype
from syntax import PatList, PatTuple
from type_syntax import (
    PRIMITIVE_SPELLINGS,
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
    TupleExpr,
    TupleType,
    Type,
    TypeExpr,
    UnionExpr,
    UnionType,
    base_type,
    literal_type,
    render,
)


def signature(d: ast.FunctionDef, mod_ctx: ModuleContext) -> CallableType:
    return CallableType(
        tuple(resolve_type(type_expr(a.annotation), a, mod_ctx) for a in d.args.args),
        resolve_type(type_expr(d.returns), d, mod_ctx),
    )


def parameters(d: ast.FunctionDef, mod_ctx: ModuleContext) -> VarContext:
    return {
        a.arg: resolve_type(type_expr(a.annotation), a, mod_ctx) for a in d.args.args
    }


def resolve_type(psi: TypeExpr, node: ast.AST, mod_ctx: ModuleContext) -> Type:
    if isinstance(psi, Primitive):
        check_in_scope(PRIMITIVE_SPELLINGS[psi], node, mod_ctx)
        return psi
    if isinstance(psi, LiteralType):
        check_in_scope("Literal", node, mod_ctx)
        return psi
    if isinstance(psi, ClassName):
        c = resolve_name(psi.q, mod_ctx)
        if not isinstance(c, Class):
            raise IllFormedModule(node, reasons.UnknownClassInAnnotation(psi.q))
        return ClassType(c)
    if isinstance(psi, ListExpr):
        check_in_scope("list", node, mod_ctx)
        return ListType(resolve_type(psi.elem, node, mod_ctx))
    if isinstance(psi, DictExpr):
        check_in_scope("dict", node, mod_ctx)
        check_in_scope("str", node, mod_ctx)
        return DictType(resolve_type(psi.value, node, mod_ctx))
    if isinstance(psi, TupleExpr):
        check_in_scope("tuple", node, mod_ctx)
        return TupleType(tuple(resolve_type(c, node, mod_ctx) for c in psi.components))
    if isinstance(psi, CallableExpr):
        check_in_scope("Callable", node, mod_ctx)
        return CallableType(
            tuple(resolve_type(p, node, mod_ctx) for p in psi.params),
            resolve_type(psi.result, node, mod_ctx),
        )
    assert isinstance(psi, UnionExpr)
    return UnionType(
        resolve_type(psi.left, node, mod_ctx), resolve_type(psi.right, node, mod_ctx)
    )


def check_in_scope(x: str, node: ast.AST, mod_ctx: ModuleContext) -> None:
    if not isinstance(mod_ctx.gamma.get(x), PredefinedName):
        raise IllFormedModule(node, reasons.AnnotationNameNotInScope(x))


def check_body(
    body: list[ast.stmt], mod_ctx: ModuleContext, returns: Type | None = None
) -> StaticOutcome:
    outcome, _ = check_seq(statements(body), mod_ctx, returns)
    return outcome


def check_top_seq(items: list[Statement], mod_ctx: ModuleContext) -> ModuleContext:
    if len(items) == 0:
        return mod_ctx
    head, tail = items[0], items[1:]
    head_outcome, sigma = check_top_statement(head, mod_ctx)
    mod_ctx_after = extend(head_outcome, replace(mod_ctx, sigma=sigma))
    if len(tail) == 0:
        return mod_ctx_after
    check_captured_reassignment(head, tail)
    delta = head_outcome.delta if isinstance(head_outcome, Assigns) else {}
    rebound = {c for c in assigns_seq(tail) if isinstance(delta.get(c), Class)}
    if len(rebound) > 0:
        node = first_assigning_statement(tail, rebound)
        raise IllFormedModule(node, reasons.ClassRebound(min(rebound)))
    return check_top_seq(tail, mod_ctx_after)


def check_top_statement(
    item: Statement, mod_ctx: ModuleContext
) -> tuple[StaticOutcome, ClassTable]:
    if isinstance(item, ast.ClassDef):
        c, sigma = class_declared(item, mod_ctx)
        return Assigns({item.name: c}), sigma
    return check_statement(item, mod_ctx, None), mod_ctx.sigma


def check_seq(
    items: list[Statement], mod_ctx: ModuleContext, returns: Type | None = None
) -> tuple[StaticOutcome, ModuleContext]:
    if len(items) == 0:
        return Assigns({}), mod_ctx
    head, tail = items[0], items[1:]
    head_outcome = check_statement(head, mod_ctx, returns)
    mod_ctx_after = extend(head_outcome, mod_ctx)
    if len(tail) == 0:
        return head_outcome, mod_ctx_after
    if isinstance(head_outcome, Returns):
        node: ast.AST = tail[0][0] if isinstance(tail[0], list) else tail[0]
        raise IllFormedModule(node, reasons.UnreachableStatement())
    check_captured_reassignment(head, tail)
    tail_outcome, final_ctx = check_seq(tail, mod_ctx_after, returns)
    return override_outcomes(head_outcome, tail_outcome), final_ctx


def check_captured_reassignment(head: Statement, tail: list[Statement]) -> None:
    reassigned = captures_statement(head) & assigns_seq(tail)
    if len(reassigned) > 0:
        node = first_assigning_statement(tail, reassigned)
        raise IllFormedModule(node, reasons.CapturedReassignment(min(reassigned)))


def extend(outcome: StaticOutcome, mod_ctx: ModuleContext) -> ModuleContext:
    return (
        override_gamma(mod_ctx, outcome.delta)
        if isinstance(outcome, Assigns)
        else mod_ctx
    )


def check_statement(
    item: Statement, mod_ctx: ModuleContext, returns: Type | None
) -> StaticOutcome:
    if isinstance(item, list):
        check_mutual_region(item, mod_ctx)
        return Assigns({d.name: signature(d, mod_ctx) for d in item})
    return check_stmt(item, mod_ctx, returns)


def check_mutual_region(defs: list[ast.FunctionDef], mod_ctx: ModuleContext) -> None:
    check_distinct_names(defs, set())
    check_bodies(defs, mod_ctx)


def check_bodies(defs: list[ast.FunctionDef], mod_ctx: ModuleContext) -> None:
    f_names: VarContext = {d.name: signature(d, mod_ctx) for d in defs}
    for d in defs:
        params = parameters(d, mod_ctx)
        locals_ = assigns_body(d.body) - set(params)
        delta = {**f_names, **params, **{x: Status.FF for x in locals_}}
        body_ctx = override_gamma(mod_ctx, delta)
        declared = resolve_type(type_expr(d.returns), d, mod_ctx)
        result = check_body(d.body, body_ctx, declared)
        if not isinstance(result, Returns):
            check_falls_off_end(mod_ctx.sigma, d, declared)


def check_falls_off_end(sigma: ClassTable, d: ast.FunctionDef, declared: Type) -> None:
    if not subtype(sigma, Primitive.NONE, declared):
        raise IllFormedModule(d, reasons.MissingReturn(d.name, render(declared)))


def check_returns_none(sigma: ClassTable, s: ast.Return, declared: Type) -> None:
    if not subtype(sigma, Primitive.NONE, declared):
        raise IllFormedModule(
            s, reasons.TypeMismatch(render(declared), render(Primitive.NONE))
        )


def check_assign_target(target: ast.Name, captured: set[str]) -> None:
    if target.id in captured:
        raise IllFormedModule(target, reasons.SelfCaptureAssignment(target.id))


def check_distinct_names(defs: list[ast.FunctionDef], seen: set[str]) -> None:
    if len(defs) == 0:
        return
    head = defs[0]
    if head.name in seen:
        raise IllFormedModule(head, reasons.DuplicateMutualName(head.name))
    check_distinct_names(defs[1:], seen | {head.name})


def check_stmt(
    s: ast.stmt, mod_ctx: ModuleContext, returns: Type | None
) -> StaticOutcome:
    if isinstance(s, ast.Pass):
        return Assigns({})
    if isinstance(s, ast.Assign):
        (target,) = s.targets
        assert isinstance(target, ast.Name)
        check_assign_target(target, captures_e(s.value))
        return Assigns({target.id: synth_expr(s.value, mod_ctx)})
    if isinstance(s, ast.AnnAssign):
        assert s.value is not None and isinstance(s.target, ast.Name)
        declared = resolve_type(type_expr(s.annotation), s, mod_ctx)
        check_expr(s.value, declared, mod_ctx)
        check_assign_target(s.target, captures_e(s.value))
        return Assigns({s.target.id: declared})
    if isinstance(s, ast.Expr):
        synth_expr(s.value, mod_ctx)
        return Assigns({})
    if isinstance(s, ast.Return):
        if returns is None:  # no return rule with empty return type
            raise IllFormedModule(s, reasons.TopLevelReturn())
        if s.value is None:
            check_returns_none(mod_ctx.sigma, s, returns)
        else:
            check_expr(s.value, returns, mod_ctx)
        return Returns()
    if isinstance(s, ast.If):
        check_expr(s.test, Primitive.BOOL, mod_ctx)
        branches = [check_body(s.body, mod_ctx, returns)]
        branches.append(
            check_body(s.orelse, mod_ctx, returns) if s.orelse else Assigns({})
        )
        return merge_outcomes(mod_ctx.sigma, branches)
    if isinstance(s, ast.Assert):
        check_expr(s.test, Primitive.BOOL, mod_ctx)
        if s.msg is not None:
            check_expr(s.msg, Primitive.STR, mod_ctx)
        return Assigns({})
    if isinstance(s, ast.Match):
        subject = synth_expr(s.subject, mod_ctx)
        return check_match_cases(s.cases, subject, mod_ctx, returns)
    raise AssertionError(f"unexpected statement: {type(s).__name__}")


def check_match_cases(
    cases: list[ast.match_case],
    subject: Type,
    mod_ctx: ModuleContext,
    returns: Type | None,
) -> StaticOutcome:
    deltas, partial = match_cases(cases, subject, mod_ctx)
    branches = [
        check_case(case, delta, mod_ctx, returns) for case, delta in zip(cases, deltas)
    ]
    return merge_outcomes(mod_ctx.sigma, branches + ([Assigns({})] if partial else []))


def match_cases(
    cases: list[ast.match_case], subject: Type, mod_ctx: ModuleContext
) -> tuple[list[VarContext], bool]:
    seed = shapes(mod_ctx.sigma, subject, frozenset())
    residual = seed
    deltas: list[VarContext] = []
    for index, case in enumerate(cases, 1):
        if not seq_safe(case.pattern, subject, mod_ctx):
            raise IllFormedModule(
                case.pattern,
                reasons.SequenceKindClash(
                    describe(case.pattern, mod_ctx), render(subject)
                ),
            )
        result = match_shapes(residual, case.pattern, mod_ctx)
        if result is None:
            raise unmatched(case.pattern, index, subject, seed, mod_ctx)
        _, residual, delta = result
        deltas.append(delta)
    return deltas, len(residual) > 0


def unmatched(
    p: ast.pattern,
    index: int,
    subject: Type,
    seed: tuple[Shape, ...],
    mod_ctx: ModuleContext,
) -> IllFormedModule:
    """A case matches nothing either because no value of the scrutinee type has
    its shape, or because the earlier cases have taken every shape it has."""
    if match_shapes(seed, p, mod_ctx) is None:
        return IllFormedModule(
            p, reasons.PatternTypeMismatch(describe(p, mod_ctx), render(subject))
        )
    return IllFormedModule(p, reasons.CaseMatchesNothing(index))


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
    if isinstance(e, ast.Name):
        if not is_assigned(mod_ctx, e.id):
            if module_of(mod_ctx, e.id) is not None:
                raise IllFormedModule(e, reasons.ModuleAsValue(e.id))
            if isinstance(mod_ctx.gamma.get(e.id), Class):
                raise IllFormedModule(e, reasons.ClassAsValue(e.id))
            if isinstance(mod_ctx.gamma.get(e.id), PredefinedName):
                raise IllFormedModule(e, reasons.PredefinedNameAsValue(e.id))
            if e.id not in mod_ctx.gamma:
                raise IllFormedModule(e, reasons.UndefinedVariable(e.id))
            raise IllFormedModule(e, reasons.UnassignedVariable(e.id))
        t = var_type(mod_ctx, e.id)
        assert t is not None
        return t
    if isinstance(e, ast.Constant):
        return LiteralType(e.value)
    if isinstance(e, ast.Lambda):
        raise IllFormedModule(e, reasons.NotSynthesised())
    if isinstance(e, ast.Call):
        constructed = class_of_name(e.func, mod_ctx)
        if constructed is not None:
            c_name, xs = short_name(constructed), fields(mod_ctx.sigma, constructed)
            kwd_names = [k.arg for k in e.keywords if k.arg is not None]
            args = field_map(
                mod_ctx.sigma,
                constructed,
                e.args,
                kwd_names,
                [k.value for k in e.keywords],
            )
            if args is None:
                n = len(e.args)
                if n + len(kwd_names) != len(xs):
                    raise IllFormedModule(
                        e,
                        reasons.ConstructorArityMismatch(
                            c_name, len(xs), n + len(kwd_names)
                        ),
                    )
                raise IllFormedModule(
                    e,
                    reasons.UnknownConstructorKeyword(
                        c_name, tuple(sorted(set(xs[n:])))
                    ),
                )
            for x, arg in args.items():
                check_expr(arg, declared_type(mod_ctx.sigma, constructed, x), mod_ctx)
            return ClassType(constructed)
        return call(e, mod_ctx)
    if isinstance(e, ast.BinOp):
        return binary(BINARY_NAMES[type(e.op)], e.left, e.right, e, mod_ctx)
    if isinstance(e, ast.UnaryOp):
        operand = synth_expr(e.operand, mod_ctx)
        negated = literal_type(e)
        if negated is not None:
            return negated
        name = UNARY_NAMES[type(e.op)]
        chosen = minimum(mod_ctx.sigma, overloads_unary(mod_ctx.sigma, name, operand))
        if chosen is None:
            raise IllFormedModule(e, reasons.NoUnaryOverload(name, render(operand)))
        _, result = chosen
        return result
    if isinstance(e, ast.BoolOp):
        for v in e.values:
            check_expr(v, Primitive.BOOL, mod_ctx)
        return Primitive.BOOL
    if isinstance(e, ast.Compare):
        assert len(e.ops) == 1
        return binary(
            BINARY_NAMES[type(e.ops[0])], e.left, e.comparators[0], e, mod_ctx
        )
    if isinstance(e, ast.IfExp):
        check_expr(e.test, Primitive.BOOL, mod_ctx)
        return branch_type(e, mod_ctx)
    if isinstance(e, ast.Attribute):
        parent = entry_of(e.value, mod_ctx)
        if isinstance(parent, ModuleLoaded):
            entry = parent.members.get(e.attr)
            if entry is None:
                raise IllFormedModule(e, reasons.UnknownMember(e.attr, parent.q))
            if isinstance(entry, ModuleStub):
                raise IllFormedModule(e, reasons.SubmoduleNotImported(entry.q))
            if isinstance(entry, ModuleLoaded):
                raise IllFormedModule(e, reasons.ModuleAsValue(qualified_name(e)))
            if isinstance(entry, Class):
                raise IllFormedModule(e, reasons.ClassAsValue(qualified_name(e)))
            if isinstance(entry, PredefinedName):
                raise IllFormedModule(
                    e, reasons.PredefinedNameAsValue(qualified_name(e))
                )
            if entry == Status.FF:
                raise IllFormedModule(e, reasons.UnassignedMember(e.attr, parent.q))
            assert not isinstance(entry, Status)
            return entry
        if isinstance(parent, ModuleStub):
            raise IllFormedModule(e, reasons.SubmoduleNotImported(parent.q))
        return field_of(synth_expr(e.value, mod_ctx), e, mod_ctx)
    if isinstance(e, ast.Subscript):
        return subscript(e, mod_ctx)
    if isinstance(e, ast.Tuple):
        return TupleType(tuple(synth_expr(x, mod_ctx) for x in e.elts))
    if isinstance(e, ast.List):
        return list_type(e, e.elts, mod_ctx)
    if isinstance(e, ast.Dict):
        for k in dict_keys(e):
            check_expr(k, Primitive.STR, mod_ctx)
        return dict_type(e, e.values, mod_ctx)
    if isinstance(e, ast.ListComp):
        return ListType(
            base_type(synth_expr(e.elt, qual_context([e.elt], e.generators, mod_ctx)))
        )
    if isinstance(e, ast.DictComp):
        mod_ctx_ = qual_context([e.key, e.value], e.generators, mod_ctx)
        check_expr(e.key, Primitive.STR, mod_ctx_)
        return DictType(base_type(synth_expr(e.value, mod_ctx_)))
    raise AssertionError(f"unexpected expression: {type(e).__name__}")


def field_of(obj: Type, e: ast.Attribute, mod_ctx: ModuleContext) -> Type:
    if isinstance(obj, UnionType):
        return join(
            mod_ctx.sigma,
            [field_of(obj.left, e, mod_ctx), field_of(obj.right, e, mod_ctx)],
        )
    if not isinstance(obj, ClassType):
        raise IllFormedModule(e, reasons.NotSynthesised())
    member = field_type(mod_ctx.sigma, obj.c, e.attr)
    if member is None:
        raise IllFormedModule(e, reasons.UnknownField(short_name(obj.c), e.attr))
    return member


def subscript(e: ast.Subscript, mod_ctx: ModuleContext) -> Type:
    return subscript_type(synth_expr(e.value, mod_ctx), e, mod_ctx)


def subscript_type(container: Type, e: ast.Subscript, mod_ctx: ModuleContext) -> Type:
    if isinstance(container, UnionType):
        return join(
            mod_ctx.sigma,
            [
                subscript_type(container.left, e, mod_ctx),
                subscript_type(container.right, e, mod_ctx),
            ],
        )
    if isinstance(container, ListType):
        check_expr(e.slice, Primitive.INT, mod_ctx)
        return container.elem
    if container == Primitive.STR:
        check_expr(e.slice, Primitive.INT, mod_ctx)
        return Primitive.STR
    if isinstance(container, DictType):
        check_expr(e.slice, Primitive.STR, mod_ctx)
        return container.value
    if isinstance(container, TupleType):
        return tuple_subscript(container, e.slice, mod_ctx)
    raise IllFormedModule(e, reasons.NotSubscriptable(render(container)))


def tuple_subscript(
    container: TupleType, index: ast.expr, mod_ctx: ModuleContext
) -> Type:
    m = len(container.components)
    actual = synth_expr(index, mod_ctx)
    i = literal_index(actual)
    if i is None:
        if actual != Primitive.INT:
            raise IllFormedModule(
                index, reasons.TypeMismatch(render(Primitive.INT), render(actual))
            )
        return join(mod_ctx.sigma, container.components)
    if not -m <= i < m:
        raise IllFormedModule(index, reasons.TupleIndexOutOfRange(i, m))
    return container.components[i]


def literal_index(t: Type) -> int | None:
    if not isinstance(t, LiteralType):
        return None
    v = t.value
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def branch_type(e: ast.IfExp, mod_ctx: ModuleContext) -> Type:
    branches = [e.body, e.orelse]
    synthesising = [x for x in branches if synthesises(x)]
    if len(synthesising) == 0:
        raise IllFormedModule(e, reasons.NotSynthesised())
    t = join(mod_ctx.sigma, [synth_expr(x, mod_ctx) for x in synthesising])
    for x in branches:
        if not synthesises(x):
            check_expr(x, t, mod_ctx)
    return t


def list_type(e: ast.expr, elts: list[ast.expr], mod_ctx: ModuleContext) -> ListType:
    synthesising = [x for x in elts if synthesises(x)]
    if len(synthesising) == 0:
        raise IllFormedModule(e, reasons.NotSynthesised())
    t = join(mod_ctx.sigma, [base_type(synth_expr(x, mod_ctx)) for x in synthesising])
    for x in elts:
        if not synthesises(x):
            check_expr(x, t, mod_ctx)
    return ListType(t)


def synthesises(e: ast.expr) -> bool:
    if isinstance(e, ast.Lambda):
        return False
    if isinstance(e, ast.IfExp):
        return synthesises(e.body) or synthesises(e.orelse)
    if isinstance(e, ast.List):
        return any(synthesises(x) for x in e.elts)
    if isinstance(e, ast.Dict):
        return any(synthesises(v) for v in e.values)
    if isinstance(e, ast.Tuple):
        return all(synthesises(x) for x in e.elts)
    if isinstance(e, ast.ListComp):
        return synthesises(e.elt)
    if isinstance(e, ast.DictComp):
        return synthesises(e.value)
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Lambda):
        return synthesises(e.func.body) and all(synthesises(a) for a in e.args)
    return True


def dict_type(e: ast.expr, values: list[ast.expr], mod_ctx: ModuleContext) -> DictType:
    return DictType(list_type(e, values, mod_ctx).elem)


def call(e: ast.Call, mod_ctx: ModuleContext) -> Type:
    if isinstance(e.func, ast.Lambda):
        return applied_lambda(e.func, e, mod_ctx)
    return result_type(synth_expr(e.func, mod_ctx), e, mod_ctx)


def result_type(fn: Type, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    if isinstance(fn, UnionType):
        return join(
            mod_ctx.sigma,
            [result_type(fn.left, e, mod_ctx), result_type(fn.right, e, mod_ctx)],
        )
    if not isinstance(fn, CallableType):
        raise IllFormedModule(e, reasons.NotCallable(render(fn)))
    if len(fn.params) != len(e.args):
        raise IllFormedModule(e, reasons.CallArityMismatch(len(fn.params), len(e.args)))
    for arg, param in zip(e.args, fn.params):
        check_expr(arg, param, mod_ctx)
    return fn.result


def applied_lambda(f: ast.Lambda, e: ast.Call, mod_ctx: ModuleContext) -> Type:
    return synth_expr(f.body, override_gamma(mod_ctx, lambda_arguments(f, e, mod_ctx)))


def lambda_arguments(f: ast.Lambda, e: ast.Call, mod_ctx: ModuleContext) -> VarContext:
    params = [a.arg for a in f.args.args]
    if len(params) != len(e.args):
        raise IllFormedModule(e, reasons.CallArityMismatch(len(params), len(e.args)))
    return {x: synth_expr(arg, mod_ctx) for x, arg in zip(params, e.args)}


def check_expr(e: ast.expr, expected: Type, mod_ctx: ModuleContext) -> None:
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Lambda):
        check_expr(
            e.func.body,
            expected,
            override_gamma(mod_ctx, lambda_arguments(e.func, e, mod_ctx)),
        )
        return
    if isinstance(e, ast.List) and isinstance(expected, ListType):
        for x in e.elts:
            check_expr(x, expected.elem, mod_ctx)
        return
    if (
        isinstance(e, ast.Tuple)
        and isinstance(expected, TupleType)
        and len(e.elts) == len(expected.components)
    ):
        for x, t in zip(e.elts, expected.components):
            check_expr(x, t, mod_ctx)
        return
    if isinstance(e, ast.Dict) and isinstance(expected, DictType):
        for k in dict_keys(e):
            check_expr(k, Primitive.STR, mod_ctx)
        for v in e.values:
            check_expr(v, expected.value, mod_ctx)
        return
    if isinstance(e, ast.Lambda):
        check_lambda(e, expected, mod_ctx)
        return
    if isinstance(e, ast.IfExp):
        check_expr(e.test, Primitive.BOOL, mod_ctx)
        check_expr(e.body, expected, mod_ctx)
        check_expr(e.orelse, expected, mod_ctx)
        return
    if isinstance(e, ast.ListComp) and isinstance(expected, ListType):
        check_expr(e.elt, expected.elem, qual_context([e.elt], e.generators, mod_ctx))
        return
    if isinstance(e, ast.DictComp) and isinstance(expected, DictType):
        mod_ctx_ = qual_context([e.key, e.value], e.generators, mod_ctx)
        check_expr(e.key, Primitive.STR, mod_ctx_)
        check_expr(e.value, expected.value, mod_ctx_)
        return
    actual = synth_expr(e, mod_ctx)
    if not subtype(mod_ctx.sigma, actual, expected):
        raise IllFormedModule(e, reasons.TypeMismatch(render(expected), render(actual)))


def check_lambda(e: ast.Lambda, expected: Type, mod_ctx: ModuleContext) -> None:
    params = [a.arg for a in e.args.args]
    if not isinstance(expected, CallableType):
        raise IllFormedModule(e, reasons.TypeMismatch(render(expected), "a lambda"))
    if len(params) != len(expected.params):
        raise IllFormedModule(
            e, reasons.TypeMismatch(render(expected), lambda_of(len(params)))
        )
    delta = dict(zip(params, expected.params))
    check_expr(e.body, expected.result, override_gamma(mod_ctx, delta))


def lambda_of(n: int) -> str:
    return f"a lambda of {n} parameter{'' if n == 1 else 's'}"


def binary(
    op: str, left: ast.expr, right: ast.expr, e: ast.expr, mod_ctx: ModuleContext
) -> Type:
    s, t = synth_expr(left, mod_ctx), synth_expr(right, mod_ctx)
    chosen = minimum(mod_ctx.sigma, overloads_binary(mod_ctx.sigma, op, s, t))
    if chosen is None:
        raise IllFormedModule(e, reasons.NoBinaryOverload(op, render(s), render(t)))
    _, result = chosen
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


def check_quals(
    generators: list[ast.comprehension], mod_ctx: ModuleContext
) -> VarContext:
    if len(generators) == 0:
        return {}
    g = generators[0]
    entry = elem_entry(g.iter, mod_ctx)
    x = target_name(g)
    if x in captures_e_list(g.ifs) | captures_quals(generators[1:]):
        raise IllFormedModule(g.target, reasons.CapturedGeneratorVariable(x))
    delta = {x: entry}
    mod_ctx_ = override_gamma(mod_ctx, delta)
    for e in g.ifs:
        check_expr(e, Primitive.BOOL, mod_ctx_)
    return {**delta, **check_quals(generators[1:], mod_ctx_)}


def elem_type(sigma: ClassTable, t: Type) -> Type | None:
    if isinstance(t, ListType):
        return t.elem
    if t == Primitive.STR:
        return Primitive.STR
    if isinstance(t, DictType):
        return Primitive.STR
    if isinstance(t, TupleType):
        return join(sigma, [base_type(c) for c in t.components])
    if isinstance(t, UnionType):
        left, right = elem_type(sigma, t.left), elem_type(sigma, t.right)
        return None if left is None or right is None else join(sigma, [left, right])
    return None


def elem_entry(e: ast.expr, mod_ctx: ModuleContext) -> Type:
    t = synth_expr(e, mod_ctx)
    elem = elem_type(mod_ctx.sigma, t)
    if elem is None:
        raise IllFormedModule(e, reasons.NotIterable(render(t)))
    return elem


def class_declared(
    node: ast.ClassDef, mod_ctx: ModuleContext
) -> tuple[Class, ClassTable]:
    if not isinstance(mod_ctx.gamma.get("dataclass"), PredefinedName):
        raise IllFormedModule(node, reasons.DecoratorNotInScope("dataclass"))
    own = tuple((x, resolve_type(psi, node, mod_ctx)) for x, psi in own_fields(node))
    names = [x for x, _ in own]
    dup = next((n for i, n in enumerate(names) if n in names[:i]), None)
    if dup is not None:
        raise IllFormedModule(node, reasons.DuplicateFieldName(dup, node.name))
    base: Class | None = None
    if len(node.bases) > 0:
        assert isinstance(node.bases[0], ast.Name)
        base_name = node.bases[0].id
        entry = mod_ctx.gamma.get(base_name)
        if not isinstance(entry, Class):
            raise IllFormedModule(node, reasons.UnknownBaseClass(base_name))
        base = entry
        clash = set(names) & set(fields(mod_ctx.sigma, base))
        if len(clash) > 0:
            raise IllFormedModule(
                node, reasons.InheritedFieldClash(min(clash), base_name)
            )
    c = Class(f"{mod_ctx.q}.{node.name}")
    assert c not in mod_ctx.sigma, "redeclaration rejected by top-seq"
    return c, {**mod_ctx.sigma, c: ClassTableEntry(own_fields=own, base=base)}


def describe(p: ast.pattern, mod_ctx: ModuleContext) -> str:
    if isinstance(p, ast.MatchAs):
        assert p.pattern is not None  # a bare variable or wildcard always matches
        return describe(p.pattern, mod_ctx)
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return f"a pattern of type {render(literal_of(p))}"
    if isinstance(p, PatList):
        return "a list pattern"
    if isinstance(p, PatTuple):
        return "a tuple pattern"
    if isinstance(p, ast.MatchMapping):
        return "a dictionary pattern"
    assert isinstance(p, ast.MatchClass)
    cls = class_of_name(p.cls, mod_ctx)
    assert cls is not None
    return f"a pattern for class {short_name(cls)}"
