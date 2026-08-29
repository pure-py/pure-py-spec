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
    own_field_types,
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
    ModuleContext,
    ModuleLoaded,
    ModuleStub,
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
from operators import BINARY_NAMES, UNARY_NAMES, resolve_binary, resolve_unary
from patterns import check_pattern_against, check_pattern_list, is_catch_all
from reasons import IllFormedModule
from subtyping import elem_type, join, subtype
from type_syntax import (
    CallableType,
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    base_type,
    parse_annotation,
    parse_annotations,
    render,
)


def annotated_type(node: ast.AnnAssign) -> VarEntry:
    """Type an annotated assignment declares, where the annotation is one we
    represent; assigned with no type yet otherwise."""
    t = parse_annotation(node.annotation)
    return Status.TT if t is None else t


def signature(d: ast.FunctionDef) -> VarEntry:
    """Callable type of a definition, from its parameter and return
    annotations; assigned with no type yet where either is missing."""
    if d.returns is None or any(a.annotation is None for a in d.args.args):
        return Status.TT
    params = parse_annotations([a.annotation for a in d.args.args if a.annotation])
    result = parse_annotation(d.returns)
    if params is None or result is None:
        return Status.TT
    return CallableType(params, result)


def parameters(d: ast.FunctionDef) -> VarContext:
    return {
        a.arg: (Status.TT if a.annotation is None else annotation_or_tt(a.annotation))
        for a in d.args.args
    }


def annotation_or_tt(e: ast.expr) -> VarEntry:
    t = parse_annotation(e)
    return Status.TT if t is None else t


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
        assigned = check_expr(s.value, ctx)
        check_assign_targets(s.targets, captures_e(s.value))
        return Assigns(
            {
                t.id: Status.TT if assigned is None else assigned
                for t in s.targets
                if isinstance(t, ast.Name)
            }
        )
    if isinstance(s, ast.AnnAssign):
        assert s.value is not None
        declared = annotated_type(s)
        checks_against(
            s.value, declared if not isinstance(declared, Status) else None, ctx
        )
        check_assign_targets([s.target], captures_e(s.value))
        target = s.target
        return Assigns({target.id: declared} if isinstance(target, ast.Name) else {})
    if isinstance(s, ast.Expr):
        check_expr(s.value, ctx)
        return ASSIGNS_EMPTY
    if isinstance(s, ast.Return):
        if s.value is None:
            check_returns_none(s, returns, ctx)
        else:
            checks_against(s.value, returns, ctx)
        return RETURNS
    if isinstance(s, ast.If):
        checks_against(s.test, Primitive.BOOL, ctx)
        branches = [check_body(s.body, ctx, returns)]
        branches.append(
            check_body(s.orelse, ctx, returns) if s.orelse else ASSIGNS_EMPTY
        )
        return merge_results(branches)
    if isinstance(s, ast.Assert):
        checks_against(s.test, Primitive.BOOL, ctx)
        if s.msg is not None:
            checks_against(s.msg, Primitive.STR, ctx)
        return ASSIGNS_EMPTY
    if isinstance(s, ast.Match):
        subject = check_expr(s.subject, ctx)
        check_pattern_list([c.pattern for c in s.cases], s, ctx)
        return check_match_cases(s.cases, subject, ctx, returns)
    if isinstance(s, ast.ClassDef):
        check_class_decl(s, ctx.gamma, ctx.q)
        return ASSIGNS_EMPTY
    raise AssertionError(f"unexpected statement: {type(s).__name__}")


def check_match_cases(
    cases: list[ast.match_case],
    subject: Type | None,
    ctx: ModuleContext,
    returns: Type | None,
) -> ResultType:
    branches = [check_case(case, subject, ctx, returns) for case in cases]
    if not is_catch_all(cases[-1].pattern):
        branches.append(ASSIGNS_EMPTY)
    return merge_results(branches)


def check_case(
    case: ast.match_case,
    subject: Type | None,
    ctx: ModuleContext,
    returns: Type | None,
) -> ResultType:
    """Result of one case: its pattern checks against the scrutinee type, and
    its body is checked under the bindings that gives."""
    delta = check_pattern_against(case.pattern, subject, ctx)
    return override_results(
        Assigns(delta), check_body(case.body, override_var(ctx, delta), returns)
    )


def check_expr(e: ast.expr, ctx: ModuleContext) -> Type | None:
    """The type of `e`, where the rules give one; None where they do not yet."""
    if isinstance(e, ast.Name):
        if not is_assigned(ctx, e.id):
            if module_of(ctx, e.id) is not None:
                raise IllFormedModule(e, reasons.ModuleAsValue(e.id))
            if class_of(ctx, e.id) is not None:
                raise IllFormedModule(e, reasons.ClassAsValue(e.id))
            raise IllFormedModule(e, reasons.UnassignedVariable(e.id))
        return var_type(ctx, e.id)
    if isinstance(e, ast.Constant):
        return LiteralType(e.value)
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        check_expr(e.body, override_var(ctx, {p: Status.TT for p in params}))
        return None
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
                checks_against(arg, field_type(constructed, x), ctx)
            return ClassType(c_name)
        return call(e, ctx)
    if isinstance(e, ast.BinOp):
        return binary(BINARY_NAMES[type(e.op)], e.left, e.right, e, ctx)
    if isinstance(e, ast.UnaryOp):
        operand = check_expr(e.operand, ctx)
        negated = negated_literal(e)
        if negated is not None:
            return negated
        name = UNARY_NAMES[type(e.op)]
        if operand is None:
            return None
        result = resolve_unary(name, operand, ctx)
        if result is None:
            raise IllFormedModule(e, reasons.NoUnarySignature(name, render(operand)))
        return result
    if isinstance(e, ast.BoolOp):
        for v in e.values:
            checks_against(v, Primitive.BOOL, ctx)
        return Primitive.BOOL
    if isinstance(e, ast.Compare):
        check_exprs(e.comparators, ctx)
        if len(e.ops) != 1:
            check_expr(e.left, ctx)
            return None
        return binary(BINARY_NAMES[type(e.ops[0])], e.left, e.comparators[0], e, ctx)
    if isinstance(e, ast.IfExp):
        checks_against(e.test, Primitive.BOOL, ctx)
        check_expr(e.body, ctx)
        check_expr(e.orelse, ctx)
        return None
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
            if entry == Status.FF:
                raise IllFormedModule(e, reasons.UnassignedMember(e.attr, parent.q))
            return None
        if isinstance(parent, ModuleStub):
            raise IllFormedModule(e, reasons.SubmoduleNotImported(parent.q))
        obj = check_expr(e.value, ctx)
        if not isinstance(obj, ClassType):
            return None
        entry = class_of(ctx, obj.q)
        return None if entry is None else field_type(entry, e.attr)
    if isinstance(e, ast.Subscript):
        return subscript(e, ctx)
    if isinstance(e, ast.Tuple):
        components = [check_expr(x, ctx) for x in e.elts]
        if any(t is None for t in components):
            return None
        return TupleType(tuple(t for t in components if t is not None))
    if isinstance(e, ast.List):
        return list_type(e.elts, ctx)
    if isinstance(e, ast.Dict):
        for k in e.keys:
            if k is not None:
                checks_against(k, Primitive.STR, ctx)
        return dict_type(e.values, ctx)
    if isinstance(e, ast.ListComp):
        t = check_expr(e.elt, qual_context([e.elt], e.generators, ctx))
        return None if t is None else ListType(base_type(t))
    if isinstance(e, ast.DictComp):
        ctx_ = qual_context([e.key, e.value], e.generators, ctx)
        checks_against(e.key, Primitive.STR, ctx_)
        t = check_expr(e.value, ctx_)
        return None if t is None else DictType(base_type(t))
    raise AssertionError(f"unexpected expression: {type(e).__name__}")


def subscript(e: ast.Subscript, ctx: ModuleContext) -> Type | None:
    """The type of a subscript, given the type of the container."""
    container = check_expr(e.value, ctx)
    if container is None:
        check_expr(e.slice, ctx)
        return None
    if isinstance(container, ListType):
        checks_against(e.slice, Primitive.INT, ctx)
        return container.elem
    if container == Primitive.STR:
        checks_against(e.slice, Primitive.INT, ctx)
        return Primitive.STR
    if isinstance(container, DictType):
        checks_against(e.slice, Primitive.STR, ctx)
        return container.value
    if isinstance(container, TupleType):
        return tuple_subscript(container, e.slice, ctx)
    raise IllFormedModule(e, reasons.NotSubscriptable(render(container)))


def tuple_subscript(
    container: TupleType, index: ast.expr, ctx: ModuleContext
) -> Type | None:
    """A literal index gives the component at that position, counting from the
    end where it is negative; any other index of type int gives their join."""
    m = len(container.components)
    i = literal_index(check_expr(index, ctx))
    if i is None:
        checks_against(index, Primitive.INT, ctx)
        return join(container.components, ctx)
    if not -m <= i < m:
        raise IllFormedModule(index, reasons.TupleIndexOutOfRange(i, m))
    return container.components[i]


def literal_index(t: Type | None) -> int | None:
    if not isinstance(t, LiteralType):
        return None
    v = t.value
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def list_type(elts: list[ast.expr], ctx: ModuleContext) -> Type | None:
    """A non-empty list synthesises where at least one element does, at the join
    of the types of those that do, with the others checked against it."""
    synthesised = [check_expr(x, ctx) for x in elts]
    known = [t for t in synthesised if t is not None]
    if len(known) == 0:
        return None
    elem = join([base_type(t) for t in known], ctx)
    for x, t in zip(elts, synthesised):
        if t is None:
            checks_against(x, elem, ctx)
    return ListType(elem)


def dict_type(values: list[ast.expr], ctx: ModuleContext) -> Type | None:
    """A non-empty dictionary synthesises where at least one value does, at the
    join of the base types of those that do, with the others checked against
    it."""
    elem = list_type(values, ctx)
    return None if not isinstance(elem, ListType) else DictType(elem.elem)


def call(e: ast.Call, ctx: ModuleContext) -> Type | None:
    """The result type of a call, checking each argument against its parameter
    type; the callee must be a callable of the same arity."""
    fn = check_expr(e.func, ctx)
    if fn is None:
        check_exprs(e.args, ctx)
        return None
    if not isinstance(fn, CallableType):
        raise IllFormedModule(e, reasons.NotCallable(render(fn)))
    if len(fn.params) != len(e.args):
        raise IllFormedModule(e, reasons.CallArityMismatch(len(fn.params), len(e.args)))
    for arg, param in zip(e.args, fn.params):
        checks_against(arg, param, ctx)
    return fn.result


def checks_against(e: ast.expr, expected: Type | None, ctx: ModuleContext) -> None:
    """Check `e` against `expected`. A container display checks its parts against
    the parts of the expected type; anything else synthesises and must be below
    it."""
    if expected is None:
        check_expr(e, ctx)
        return
    if isinstance(e, ast.List) and isinstance(expected, ListType):
        for x in e.elts:
            checks_against(x, expected.elem, ctx)
        return
    if (
        isinstance(e, ast.Tuple)
        and isinstance(expected, TupleType)
        and len(e.elts) == len(expected.components)
    ):
        for x, t in zip(e.elts, expected.components):
            checks_against(x, t, ctx)
        return
    if isinstance(e, ast.Dict) and isinstance(expected, DictType):
        for k in e.keys:
            if k is not None:
                checks_against(k, Primitive.STR, ctx)
        for v in e.values:
            checks_against(v, expected.value, ctx)
        return
    if isinstance(e, ast.Lambda):
        check_lambda(e, expected, ctx)
        return
    if isinstance(e, ast.IfExp):
        checks_against(e.test, Primitive.BOOL, ctx)
        checks_against(e.body, expected, ctx)
        checks_against(e.orelse, expected, ctx)
        return
    if isinstance(e, ast.ListComp) and isinstance(expected, ListType):
        checks_against(e.elt, expected.elem, qual_context([e.elt], e.generators, ctx))
        return
    if isinstance(e, ast.DictComp) and isinstance(expected, DictType):
        ctx_ = qual_context([e.key, e.value], e.generators, ctx)
        checks_against(e.key, Primitive.STR, ctx_)
        checks_against(e.value, expected.value, ctx_)
        return
    actual = check_expr(e, ctx)
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
    checks_against(e.body, expected.result, override_var(ctx, delta))


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
) -> Type | None:
    s, t = check_expr(left, ctx), check_expr(right, ctx)
    if s is None or t is None:
        return None
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
        checks_against(e, Primitive.BOOL, ctx_)
    return delta | check_quals(generators[1:], ctx_)


def elem_entry(e: ast.expr, ctx: ModuleContext) -> VarEntry:
    """Type a generator binds its target at, where the type of what it draws
    from is known."""
    t = check_expr(e, ctx)
    if t is None:
        return Status.TT
    elem = elem_type(t, ctx)
    if elem is None:
        raise IllFormedModule(e, reasons.NotIterable(render(t)))
    return elem


def check_exprs(es: list[ast.expr], ctx: ModuleContext) -> None:
    if len(es) == 0:
        return
    check_expr(es[0], ctx)
    check_exprs(es[1:], ctx)


def class_entry_for(node: ast.ClassDef, q: str, context: Context) -> ClassEntry:
    base = (
        node.bases[0].id if node.bases and isinstance(node.bases[0], ast.Name) else None
    )
    return ClassEntry(
        context=context,
        name=f"{q}.{node.name}",
        own_fields=tuple(own_fields(node)),
        own_types=own_field_types(node),
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
