import ast

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
    find_first_reassigning,
    names_in_target,
    own_fields,
    qualified_name,
    statements,
)
from contexts import (
    ASSIGNS_EMPTY,
    RETURNS,
    Assigns,
    ClassEntry,
    Context,
    Join,
    ModuleContext,
    ModuleLoaded,
    ModuleStub,
    PredefinedName,
    ResultType,
    Returns,
    Status,
    VarContext,
    VarEntry,
    class_entry,
    class_of,
    entry_of,
    field_map,
    field_type,
    fields,
    is_assigned,
    merge_results,
    module_of,
    override_gamma,
    override_results,
    override_var,
    short_name,
    var_type,
)
from match import literal_of, match_shapes
from operators import BINARY_NAMES, UNARY_NAMES, resolve_binary, resolve_unary
from reasons import IllFormedModule
from shapes import Shape, shapes
from subtyping import elem_type, join, subtype
from syntax import PatList, PatTuple
from type_syntax import (
    PRIMITIVE_SPELLINGS,
    CallableType,
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
    base_type,
    parse_annotation,
    parse_annotations,
    render,
)


def annotated_type(node: ast.AnnAssign) -> Type:
    """Type an annotated assignment declares. Every annotation the subset
    admits denotes a type."""
    t = parse_annotation(node.annotation)
    assert t is not None
    return t


def signature(d: ast.FunctionDef) -> VarEntry:
    """Callable type of a definition, from its parameter and return
    annotations; assigned with no type yet where either is missing."""
    if d.returns is None or any(a.annotation is None for a in d.args.args):
        return Status.TT
    params = parse_annotations([a.annotation for a in d.args.args if a.annotation])
    result = parse_annotation(d.returns)
    assert params is not None and result is not None
    return CallableType(params, result)


def parameters(d: ast.FunctionDef) -> VarContext:
    return {
        a.arg: (Status.TT if a.annotation is None else annotated(a.annotation))
        for a in d.args.args
    }


def well_formed(t: Type, node: ast.AST, ctx: ModuleContext) -> Type:
    """Check that annotation `t` is well-formed: each name it is written with is
    in scope, a class name bound to a class entry and every other spelling to the
    entry its module gives it."""
    if isinstance(t, Primitive):
        in_scope(PRIMITIVE_SPELLINGS[t], node, ctx)
    elif isinstance(t, LiteralType):
        in_scope("Literal", node, ctx)
    elif isinstance(t, ClassType):
        if class_of(ctx, t.q) is None:
            raise IllFormedModule(node, reasons.UnknownClassInAnnotation(t.q))
    elif isinstance(t, ListType):
        in_scope("list", node, ctx)
        well_formed(t.elem, node, ctx)
    elif isinstance(t, DictType):
        in_scope("dict", node, ctx)
        in_scope("str", node, ctx)
        well_formed(t.value, node, ctx)
    elif isinstance(t, TupleType):
        in_scope("tuple", node, ctx)
        for c in t.components:
            well_formed(c, node, ctx)
    elif isinstance(t, CallableType):
        in_scope("Callable", node, ctx)
        for param in t.params:
            well_formed(param, node, ctx)
        well_formed(t.result, node, ctx)
    elif isinstance(t, UnionType):
        well_formed(t.left, node, ctx)
        well_formed(t.right, node, ctx)
    return t


def in_scope(x: str, node: ast.AST, ctx: ModuleContext) -> None:
    """A name an annotation is written with must still be the predefined one,
    which an import brings into scope and an assignment takes away."""
    if not isinstance(ctx.gamma.get(x), PredefinedName):
        raise IllFormedModule(node, reasons.AnnotationNameNotInScope(x))


def annotated(e: ast.expr) -> Type:
    """Type an annotation denotes; the subset admits no other annotation."""
    t = parse_annotation(e)
    assert t is not None
    return t


def check_body(
    body: list[ast.stmt], ctx: ModuleContext, returns: Type | None = None
) -> ResultType:
    """Check a body in a function declared to return `returns`, or at the top
    level of a module, where a return is not allowed at all."""
    result, _ = check_seq(statements(body), ctx, returns)
    return result


def check_seq(
    items: list[Statement], ctx: ModuleContext, returns: Type | None = None
) -> tuple[ResultType, ModuleContext]:
    """Check a sequence, threading the context through it, and give its result
    type and the context after it; nothing may follow a statement that
    definitely returns."""
    if len(items) == 0:
        return ASSIGNS_EMPTY, ctx
    head, tail = items[0], items[1:]
    head_result = check_statement(head, ctx, returns)
    ctx_after = extend(head, head_result, ctx)
    if len(tail) == 0:
        return head_result, ctx_after
    if isinstance(head_result, Returns):
        node: ast.AST = tail[0][0] if isinstance(tail[0], list) else tail[0]
        raise IllFormedModule(node, reasons.UnreachableStatement())
    reassigned = captures_statement(head) & assigns_seq(tail)
    if reassigned:
        name = min(reassigned)
        ra_node = find_first_reassigning(tail, reassigned)
        assert ra_node is not None
        raise IllFormedModule(ra_node, reasons.CapturedReassignment(name))
    tail_result, final_ctx = check_seq(tail, ctx_after, returns)
    return override_results(head_result, tail_result), final_ctx


def extend(head: Statement, result: ResultType, ctx: ModuleContext) -> ModuleContext:
    # A class declaration assigns a class entry, which a result type cannot carry.
    if isinstance(head, ast.ClassDef):
        return override_gamma(ctx, {head.name: class_entry_for(head, ctx.q, ctx.gamma)})
    return override_var(ctx, result.delta if isinstance(result, Assigns) else {})


def check_statement(
    item: Statement, ctx: ModuleContext, returns: Type | None
) -> ResultType:
    if isinstance(item, list):
        check_mutual_region(item, ctx)
        return Assigns({d.name: signature(d) for d in item})
    return check_stmt(item, ctx, returns)


def check_mutual_region(defs: list[ast.FunctionDef], ctx: ModuleContext) -> None:
    check_distinct_names(defs, set())
    check_annotated(defs)
    check_bodies(defs, ctx)


def check_annotated(defs: list[ast.FunctionDef]) -> None:
    """Every parameter and return carries an annotation, so the type of a
    definition is given rather than inferred from its body."""
    for d in defs:
        if isinstance(signature(d), Status):
            raise IllFormedModule(d, reasons.MissingAnnotation(d.name))


def check_bodies(defs: list[ast.FunctionDef], ctx: ModuleContext) -> None:
    f_names: VarContext = {d.name: signature(d) for d in defs}
    for d in defs:
        params = parameters(d)
        for a in d.args.args:
            assert a.annotation is not None
            well_formed(annotated(a.annotation), a, ctx)
        assert d.returns is not None
        well_formed(annotated(d.returns), d, ctx)
        locals_ = assigns_body(d.body) - set(params)
        delta = f_names | params | {x: Status.FF for x in locals_}
        body_ctx = override_var(ctx, delta)
        declared = declared_return(d)
        result = check_body(d.body, body_ctx, declared)
        if not isinstance(result, Returns):
            check_falls_off_end(d, declared, ctx)


def declared_return(d: ast.FunctionDef) -> Type | None:
    return None if d.returns is None else parse_annotation(d.returns)


def check_falls_off_end(
    d: ast.FunctionDef, declared: Type | None, ctx: ModuleContext
) -> None:
    """A body that does not definitely return falls off the end, giving None,
    so the declared type must admit it."""
    if declared is not None and not subtype(Primitive.NONE, declared, ctx):
        raise IllFormedModule(d, reasons.MissingReturn(d.name, render(declared)))


def check_returns_none(
    s: ast.Return, declared: Type | None, ctx: ModuleContext
) -> None:
    if declared is not None and not subtype(Primitive.NONE, declared, ctx):
        raise IllFormedModule(
            s, reasons.TypeMismatch(render(declared), render(Primitive.NONE))
        )


def check_assign_targets(targets: list[ast.expr], captured: set[str]) -> None:
    if len(targets) == 0:
        return
    t = targets[0]
    if isinstance(t, ast.Name) and t.id in captured:
        raise IllFormedModule(t, reasons.SelfCaptureAssignment(t.id))
    check_assign_targets(targets[1:], captured)


def check_distinct_names(defs: list[ast.FunctionDef], seen: set[str]) -> None:
    if len(defs) == 0:
        return
    head = defs[0]
    if head.name in seen:
        raise IllFormedModule(head, reasons.DuplicateMutualName(head.name))
    check_distinct_names(defs[1:], seen | {head.name})


def check_stmt(s: ast.stmt, ctx: ModuleContext, returns: Type | None) -> ResultType:
    if isinstance(s, ast.Pass):
        return ASSIGNS_EMPTY
    if isinstance(s, ast.Assign):
        check_assign_targets(s.targets, captures_e(s.value))
        assigned = synth_expr(s.value, ctx)
        return Assigns({t.id: assigned for t in s.targets if isinstance(t, ast.Name)})
    if isinstance(s, ast.AnnAssign):
        assert s.value is not None
        declared = well_formed(annotated_type(s), s, ctx)
        check_expr(s.value, declared, ctx)
        check_assign_targets([s.target], captures_e(s.value))
        target = s.target
        return Assigns({target.id: declared} if isinstance(target, ast.Name) else {})
    if isinstance(s, ast.Expr):
        synth_expr(s.value, ctx)
        return ASSIGNS_EMPTY
    if isinstance(s, ast.Return):
        if s.value is None:
            check_returns_none(s, returns, ctx)
        else:
            assert returns is not None
            check_expr(s.value, returns, ctx)
        return RETURNS
    if isinstance(s, ast.If):
        check_expr(s.test, Primitive.BOOL, ctx)
        branches = [check_body(s.body, ctx, returns)]
        branches.append(
            check_body(s.orelse, ctx, returns) if s.orelse else ASSIGNS_EMPTY
        )
        return merge_results(branches, joiner(ctx))
    if isinstance(s, ast.Assert):
        check_expr(s.test, Primitive.BOOL, ctx)
        if s.msg is not None:
            check_expr(s.msg, Primitive.STR, ctx)
        return ASSIGNS_EMPTY
    if isinstance(s, ast.Match):
        subject = synth_expr(s.subject, ctx)
        return check_match_cases(s.cases, subject, ctx, returns)
    if isinstance(s, ast.ClassDef):
        check_class_decl(s, ctx.gamma, ctx.q)
        return ASSIGNS_EMPTY
    raise AssertionError(f"unexpected statement: {type(s).__name__}")


def joiner(ctx: ModuleContext) -> Join:
    """Join at this context, for merging the branches of a conditional."""
    return lambda s, t: join([s, t], ctx)


def check_match_cases(
    cases: list[ast.match_case],
    subject: Type,
    ctx: ModuleContext,
    returns: Type | None,
) -> ResultType:
    deltas, partial = match_cases(cases, subject, ctx)
    branches = [
        check_case(case, delta, ctx, returns) for case, delta in zip(cases, deltas)
    ]
    return merge_results(branches + ([ASSIGNS_EMPTY] if partial else []), joiner(ctx))


def match_cases(
    cases: list[ast.match_case], subject: Type, ctx: ModuleContext
) -> tuple[list[VarContext], bool]:
    """Bindings of each case, taken by matching against the residual, and
    whether some value of the scrutinee type falls through."""
    seed = shapes(base_type(subject), frozenset(), ctx)
    left = seed
    deltas: list[VarContext] = []
    for index, case in enumerate(cases, 1):
        result = match_shapes(left, case.pattern, ctx)
        if result is None:
            raise unmatched(case.pattern, index, subject, seed, ctx)
        _, left, delta = result
        deltas.append(delta)
    return deltas, len(left) > 0


def unmatched(
    p: ast.pattern,
    index: int,
    subject: Type,
    seed: frozenset[Shape],
    ctx: ModuleContext,
) -> IllFormedModule:
    """A case matches nothing either because no value of the scrutinee type has
    its shape, or because the earlier cases have taken every shape it has."""
    if match_shapes(seed, p, ctx) is None:
        return IllFormedModule(
            p, reasons.PatternTypeMismatch(describe(p, ctx), render(subject))
        )
    return IllFormedModule(p, reasons.CaseMatchesNothing(index))


def check_case(
    case: ast.match_case,
    delta: VarContext,
    ctx: ModuleContext,
    returns: Type | None,
) -> ResultType:
    """Result of one case, whose body is checked under the bindings its pattern
    gives."""
    return override_results(
        Assigns(delta), check_body(case.body, override_var(ctx, delta), returns)
    )


def synth_expr(e: ast.expr, ctx: ModuleContext) -> Type:
    """Type `e` synthesises. An expression with no synthesis rule, such as a
    lambda or an empty list, is rejected here and must be checked instead."""
    if isinstance(e, ast.Name):
        if not is_assigned(ctx, e.id):
            if module_of(ctx, e.id) is not None:
                raise IllFormedModule(e, reasons.ModuleAsValue(e.id))
            if class_of(ctx, e.id) is not None:
                raise IllFormedModule(e, reasons.ClassAsValue(e.id))
            if isinstance(ctx.gamma.get(e.id), PredefinedName):
                raise IllFormedModule(e, reasons.PredefinedNameAsValue(e.id))
            if e.id not in ctx.gamma:
                raise IllFormedModule(e, reasons.UndefinedVariable(e.id))
            raise IllFormedModule(e, reasons.UnassignedVariable(e.id))
        t = var_type(ctx, e.id)
        if t is None:
            raise IllFormedModule(e, reasons.NotSynthesised())
        return t
    if isinstance(e, ast.Constant):
        return LiteralType(e.value)
    if isinstance(e, ast.Lambda):
        raise IllFormedModule(e, reasons.NotSynthesised())
    if isinstance(e, ast.Call):
        constructed = class_entry(e.func, ctx)
        if constructed is not None:
            c_name, xs = short_name(constructed), fields(constructed)
            kwd_names = [k.arg for k in e.keywords if k.arg is not None]
            if (
                field_map(constructed, e.args, kwd_names, [k.value for k in e.keywords])
                is None
            ):
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
            args = field_map(
                constructed, e.args, kwd_names, [k.value for k in e.keywords]
            )
            assert args is not None
            for x, arg in args.items():
                declared = field_type(constructed, x)
                assert declared is not None
                check_expr(arg, declared, ctx)
            return ClassType(c_name)
        return call(e, ctx)
    if isinstance(e, ast.BinOp):
        return binary(BINARY_NAMES[type(e.op)], e.left, e.right, e, ctx)
    if isinstance(e, ast.UnaryOp):
        operand = synth_expr(e.operand, ctx)
        negated = negated_literal(e)
        if negated is not None:
            return negated
        name = UNARY_NAMES[type(e.op)]
        result = resolve_unary(name, operand, ctx)
        if result is None:
            raise IllFormedModule(e, reasons.NoUnarySignature(name, render(operand)))
        return result
    if isinstance(e, ast.BoolOp):
        for v in e.values:
            check_expr(v, Primitive.BOOL, ctx)
        return Primitive.BOOL
    if isinstance(e, ast.Compare):
        assert len(e.ops) == 1
        return binary(BINARY_NAMES[type(e.ops[0])], e.left, e.comparators[0], e, ctx)
    if isinstance(e, ast.IfExp):
        check_expr(e.test, Primitive.BOOL, ctx)
        raise IllFormedModule(e, reasons.NotSynthesised())
    if isinstance(e, ast.Attribute):
        parent = entry_of(e.value, ctx)
        if isinstance(parent, ModuleLoaded):
            entry = parent.members.get(e.attr)
            if entry is None:
                raise IllFormedModule(e, reasons.UnknownMember(e.attr, parent.q))
            if isinstance(entry, ModuleStub):
                raise IllFormedModule(e, reasons.SubmoduleNotImported(entry.q))
            if isinstance(entry, ModuleLoaded):
                raise IllFormedModule(e, reasons.ModuleAsValue(qualified_name(e)))
            if isinstance(entry, ClassEntry):
                raise IllFormedModule(e, reasons.ClassAsValue(qualified_name(e)))
            if isinstance(entry, PredefinedName):
                raise IllFormedModule(
                    e, reasons.PredefinedNameAsValue(qualified_name(e))
                )
            if entry == Status.FF:
                raise IllFormedModule(e, reasons.UnassignedMember(e.attr, parent.q))
            if isinstance(entry, (Status, PredefinedName)):
                raise IllFormedModule(e, reasons.NotSynthesised())
            return entry
        if isinstance(parent, ModuleStub):
            raise IllFormedModule(e, reasons.SubmoduleNotImported(parent.q))
        obj = synth_expr(e.value, ctx)
        entry = class_of(ctx, obj.q) if isinstance(obj, ClassType) else None
        if entry is None:
            raise IllFormedModule(e, reasons.NotSynthesised())
        member = field_type(entry, e.attr)
        if member is None:
            raise IllFormedModule(e, reasons.UnknownField(short_name(entry), e.attr))
        return member
    if isinstance(e, ast.Subscript):
        return subscript(e, ctx)
    if isinstance(e, ast.Tuple):
        return TupleType(tuple(synth_expr(x, ctx) for x in e.elts))
    if isinstance(e, ast.List):
        return list_type(e, e.elts, ctx)
    if isinstance(e, ast.Dict):
        for k in e.keys:
            if k is not None:
                check_expr(k, Primitive.STR, ctx)
        return dict_type(e, e.values, ctx)
    if isinstance(e, ast.ListComp):
        return ListType(
            base_type(synth_expr(e.elt, qual_context([e.elt], e.generators, ctx)))
        )
    if isinstance(e, ast.DictComp):
        ctx_ = qual_context([e.key, e.value], e.generators, ctx)
        check_expr(e.key, Primitive.STR, ctx_)
        return DictType(base_type(synth_expr(e.value, ctx_)))
    raise AssertionError(f"unexpected expression: {type(e).__name__}")


def subscript(e: ast.Subscript, ctx: ModuleContext) -> Type:
    """The type of a subscript, given the type of the container."""
    container = synth_expr(e.value, ctx)
    if isinstance(container, ListType):
        check_expr(e.slice, Primitive.INT, ctx)
        return container.elem
    if container == Primitive.STR:
        check_expr(e.slice, Primitive.INT, ctx)
        return Primitive.STR
    if isinstance(container, DictType):
        check_expr(e.slice, Primitive.STR, ctx)
        return container.value
    if isinstance(container, TupleType):
        return tuple_subscript(container, e.slice, ctx)
    raise IllFormedModule(e, reasons.NotSubscriptable(render(container)))


def tuple_subscript(container: TupleType, index: ast.expr, ctx: ModuleContext) -> Type:
    """A literal index gives the component at that position, counting from the
    end where it is negative; any other index of type int gives their join."""
    m = len(container.components)
    i = literal_index(synth_expr(index, ctx))
    if i is None:
        check_expr(index, Primitive.INT, ctx)
        return join(container.components, ctx)
    if not -m <= i < m:
        raise IllFormedModule(index, reasons.TupleIndexOutOfRange(i, m))
    return container.components[i]


def literal_index(t: Type) -> int | None:
    if not isinstance(t, LiteralType):
        return None
    v = t.value
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def list_type(e: ast.expr, elts: list[ast.expr], ctx: ModuleContext) -> ListType:
    """A non-empty list synthesises at the join of the base types of its
    elements; an empty one has no synthesis rule."""
    if len(elts) == 0:
        raise IllFormedModule(e, reasons.NotSynthesised())
    return ListType(join([base_type(synth_expr(x, ctx)) for x in elts], ctx))


def dict_type(e: ast.expr, values: list[ast.expr], ctx: ModuleContext) -> DictType:
    """A non-empty dictionary synthesises at the join of the base types of its
    values; an empty one has no synthesis rule."""
    return DictType(list_type(e, values, ctx).elem)


def call(e: ast.Call, ctx: ModuleContext) -> Type:
    """The result type of a call, checking each argument against its parameter
    type; the callee must be a callable of the same arity."""
    if isinstance(e.func, ast.Lambda):
        return applied_lambda(e.func, e, ctx)
    fn = synth_expr(e.func, ctx)
    if not isinstance(fn, CallableType):
        raise IllFormedModule(e, reasons.NotCallable(render(fn)))
    if len(fn.params) != len(e.args):
        raise IllFormedModule(e, reasons.CallArityMismatch(len(fn.params), len(e.args)))
    for arg, param in zip(e.args, fn.params):
        check_expr(arg, param, ctx)
    return fn.result


def applied_lambda(f: ast.Lambda, e: ast.Call, ctx: ModuleContext) -> Type:
    """A lambda applied to arguments takes its parameter types from the types
    the arguments synthesise, and gives the type of its body."""
    return synth_expr(f.body, override_var(ctx, lambda_arguments(f, e, ctx)))


def lambda_arguments(f: ast.Lambda, e: ast.Call, ctx: ModuleContext) -> VarContext:
    """Parameters of an applied lambda, at the types its arguments synthesise."""
    params = [a.arg for a in f.args.args]
    if len(params) != len(e.args):
        raise IllFormedModule(e, reasons.CallArityMismatch(len(params), len(e.args)))
    return {x: synth_expr(arg, ctx) for x, arg in zip(params, e.args)}


def check_expr(e: ast.expr, expected: Type, ctx: ModuleContext) -> None:
    """Check `e` against `expected`. A container display checks its parts against
    the parts of the expected type; anything else synthesises and must be below
    it."""
    if expected is None:
        synth_expr(e, ctx)
        return
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Lambda):
        check_expr(
            e.func.body, expected, override_var(ctx, lambda_arguments(e.func, e, ctx))
        )
        return
    if isinstance(e, ast.List) and isinstance(expected, ListType):
        for x in e.elts:
            check_expr(x, expected.elem, ctx)
        return
    if (
        isinstance(e, ast.Tuple)
        and isinstance(expected, TupleType)
        and len(e.elts) == len(expected.components)
    ):
        for x, t in zip(e.elts, expected.components):
            check_expr(x, t, ctx)
        return
    if isinstance(e, ast.Dict) and isinstance(expected, DictType):
        for k in e.keys:
            if k is not None:
                check_expr(k, Primitive.STR, ctx)
        for v in e.values:
            check_expr(v, expected.value, ctx)
        return
    if isinstance(e, ast.Lambda):
        check_lambda(e, expected, ctx)
        return
    if isinstance(e, ast.IfExp):
        check_expr(e.test, Primitive.BOOL, ctx)
        check_expr(e.body, expected, ctx)
        check_expr(e.orelse, expected, ctx)
        return
    if isinstance(e, ast.ListComp) and isinstance(expected, ListType):
        check_expr(e.elt, expected.elem, qual_context([e.elt], e.generators, ctx))
        return
    if isinstance(e, ast.DictComp) and isinstance(expected, DictType):
        ctx_ = qual_context([e.key, e.value], e.generators, ctx)
        check_expr(e.key, Primitive.STR, ctx_)
        check_expr(e.value, expected.value, ctx_)
        return
    actual = synth_expr(e, ctx)
    if actual is None:
        return
    if not subtype(actual, expected, ctx):
        raise IllFormedModule(e, reasons.TypeMismatch(render(expected), render(actual)))


def check_lambda(e: ast.Lambda, expected: Type, ctx: ModuleContext) -> None:
    """Check a lambda against a callable type, binding each parameter at the
    type the callable gives it."""
    params = [a.arg for a in e.args.args]
    if not isinstance(expected, CallableType):
        raise IllFormedModule(e, reasons.TypeMismatch(render(expected), "a lambda"))
    if len(params) != len(expected.params):
        raise IllFormedModule(
            e, reasons.TypeMismatch(render(expected), lambda_of(len(params)))
        )
    delta = dict(zip(params, expected.params))
    check_expr(e.body, expected.result, override_var(ctx, delta))


def lambda_of(n: int) -> str:
    return f"a lambda of {n} parameter{'' if n == 1 else 's'}"


def negated_literal(e: ast.UnaryOp) -> Type | None:
    """A negated numeric literal synthesises the negated literal type."""
    if not isinstance(e.op, ast.USub) or not isinstance(e.operand, ast.Constant):
        return None
    v = e.operand.value
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return LiteralType(-v)


def binary(
    op: str, left: ast.expr, right: ast.expr, e: ast.expr, ctx: ModuleContext
) -> Type:
    s, t = synth_expr(left, ctx), synth_expr(right, ctx)
    result = resolve_binary(op, s, t, ctx)
    if result is None:
        raise IllFormedModule(e, reasons.NoBinarySignature(op, render(s), render(t)))
    return result


def qual_context(
    elts: list[ast.expr], generators: list[ast.comprehension], ctx: ModuleContext
) -> ModuleContext:
    """Context a comprehension body is typed in, extended by the bindings of its
    qualifiers."""
    delta = check_quals(generators, ctx)
    captured = captures_e_list(elts) & binds_quals(generators)
    if captured:
        node = generators[0].target
        raise IllFormedModule(node, reasons.CapturedGeneratorVariable(min(captured)))
    return override_var(ctx, delta)


def check_quals(generators: list[ast.comprehension], ctx: ModuleContext) -> VarContext:
    """Bindings the qualifiers introduce, each generator binding its target at
    the element type of the value it draws from."""
    if len(generators) == 0:
        return {}
    g = generators[0]
    entry = elem_entry(g.iter, ctx)
    targets = names_in_target(g.target)
    captured = targets & (captures_e_list(g.ifs) | captures_quals(generators[1:]))
    if captured:
        raise IllFormedModule(
            g.target, reasons.CapturedGeneratorVariable(min(captured))
        )
    delta = {n: entry for n in targets}
    ctx_ = override_var(ctx, delta)
    for e in g.ifs:
        check_expr(e, Primitive.BOOL, ctx_)
    return delta | check_quals(generators[1:], ctx_)


def elem_entry(e: ast.expr, ctx: ModuleContext) -> Type:
    """Type a generator binds its target at."""
    t = synth_expr(e, ctx)
    elem = elem_type(t, ctx)
    if elem is None:
        raise IllFormedModule(e, reasons.NotIterable(render(t)))
    return elem


def check_exprs(es: list[ast.expr], ctx: ModuleContext) -> None:
    if len(es) == 0:
        return
    synth_expr(es[0], ctx)
    check_exprs(es[1:], ctx)


def class_entry_for(node: ast.ClassDef, q: str, context: Context) -> ClassEntry:
    base = (
        node.bases[0].id if node.bases and isinstance(node.bases[0], ast.Name) else None
    )
    return ClassEntry(
        context=context,
        name=f"{q}.{node.name}",
        own_fields=own_fields(node),
        base=base,
    )


def check_class_decl(node: ast.ClassDef, gamma: Context, q: str) -> None:
    if isinstance(gamma.get(node.name), ClassEntry):
        raise IllFormedModule(node, reasons.DuplicateClassName(node.name, q))
    if not isinstance(gamma.get("dataclass"), PredefinedName):
        raise IllFormedModule(node, reasons.DecoratorNotInScope("dataclass"))
    for _, t in own_fields(node):
        well_formed(t, node, ModuleContext(gamma=gamma, q=q))
    names = [x for x, _ in own_fields(node)]
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


def describe(p: ast.pattern, ctx: ModuleContext) -> str:
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return f"a pattern of type {render(LiteralType(literal_of(p)))}"
    if isinstance(p, PatList):
        return "a list pattern"
    if isinstance(p, PatTuple):
        return "a tuple pattern"
    if isinstance(p, ast.MatchMapping):
        return "a dictionary pattern"
    assert isinstance(p, ast.MatchClass)
    entry = class_entry(p.cls, ctx)
    assert entry is not None
    return f"a pattern for class {short_name(entry)}"
