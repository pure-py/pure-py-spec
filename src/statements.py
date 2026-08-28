import ast

import reasons
from aux import (
    Statement,
    assigns_body,
    assigns_seq,
    binds,
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
from operators import BINARY_NAMES, UNARY_NAMES, binary_type, unary_type
from patterns import check_pattern_list, is_catch_all
from reasons import IllFormedModule
from subtyping import subtype
from type_syntax import (
    CallableType,
    ClassType,
    LiteralType,
    Primitive,
    Type,
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


def result_type(node: ast.stmt) -> ResultType:
    if isinstance(node, ast.Pass):
        return ASSIGNS_EMPTY
    if isinstance(node, ast.Assign):
        return Assigns(
            {t.id: Status.TT for t in node.targets if isinstance(t, ast.Name)}
        )
    if isinstance(node, ast.AnnAssign):
        target = node.target
        return Assigns(
            {target.id: annotated_type(node)} if isinstance(target, ast.Name) else {}
        )
    if isinstance(node, ast.Expr):
        return ASSIGNS_EMPTY
    if isinstance(node, ast.Assert):
        return ASSIGNS_EMPTY
    if isinstance(node, ast.Return):
        return RETURNS
    if isinstance(node, ast.FunctionDef):
        return Assigns({node.name: signature(node)})
    if isinstance(node, ast.If):
        return merge_results(
            [
                result_type_body(node.body),
                result_type_body(node.orelse) if node.orelse else ASSIGNS_EMPTY,
            ]
        )
    if isinstance(node, ast.Match):
        branches = [
            override_results(
                Assigns({x: Status.TT for x in binds(case.pattern)}),
                result_type_body(case.body),
            )
            for case in node.cases
        ]
        if not is_catch_all(node.cases[-1].pattern):
            branches.append(ASSIGNS_EMPTY)
        return merge_results(branches)
    if isinstance(node, ast.ClassDef):
        return ASSIGNS_EMPTY
    raise AssertionError(f"unexpected statement: {type(node).__name__}")


def result_type_body(body: list[ast.stmt]) -> ResultType:
    if len(body) == 1:
        return result_type(body[0])
    return override_results(result_type(body[0]), result_type_body(body[1:]))


def check_body(body: list[ast.stmt], ctx: ModuleContext) -> ModuleContext:
    return check_seq(statements(body), ctx)


def check_seq(items: list[Statement], ctx: ModuleContext) -> ModuleContext:
    if len(items) == 0:
        return ctx
    head = items[0]
    check_statement(head, ctx)
    if len(items) == 1:
        return next_ctx_after(head, ctx)
    tail = items[1:]
    if isinstance(result_type_statement(head), Returns):
        first_unreachable = tail[0]
        node: ast.AST = (
            first_unreachable[0]
            if isinstance(first_unreachable, list)
            else first_unreachable
        )
        raise IllFormedModule(node, reasons.UnreachableStatement())
    reassigned = captures_statement(head) & assigns_seq(tail)
    if reassigned:
        name = min(reassigned)
        ra_node = find_first_reassigning(tail, reassigned)
        assert ra_node is not None
        raise IllFormedModule(ra_node, reasons.CapturedReassignment(name))
    return check_seq(tail, next_ctx_after(head, ctx))


def next_ctx_after(head: Statement, ctx: ModuleContext) -> ModuleContext:
    # Assigns {c: C} for a class statement: ResultType carries statuses only, so the class entry is
    # added here rather than through the result type.
    if isinstance(head, ast.ClassDef):
        return override_gamma(ctx, {head.name: class_entry_for(head, ctx.q, ctx.gamma)})
    head_result = result_type_statement(head)
    delta = head_result.delta if isinstance(head_result, Assigns) else {}
    return override_var(ctx, delta)


def result_type_statement(item: Statement) -> ResultType:
    if isinstance(item, list):
        return Assigns({d.name: signature(d) for d in item})
    return result_type(item)


def check_statement(item: Statement, ctx: ModuleContext) -> None:
    if isinstance(item, list):
        check_mutual_region(item, ctx)
    else:
        check_stmt(item, ctx)


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
        check_body(d.body, body_ctx)


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


def check_stmt(s: ast.stmt, ctx: ModuleContext) -> None:
    if isinstance(s, ast.Pass):
        return
    if isinstance(s, ast.Assign):
        check_expr(s.value, ctx)
        check_assign_targets(s.targets, captures_e(s.value))
        return
    if isinstance(s, ast.AnnAssign):
        assert s.value is not None
        check_expr(s.value, ctx)
        check_assign_targets([s.target], captures_e(s.value))
        return
    if isinstance(s, ast.Expr):
        check_expr(s.value, ctx)
        return
    if isinstance(s, ast.Return):
        if s.value is not None:
            check_expr(s.value, ctx)
        return
    if isinstance(s, ast.If):
        check_expr(s.test, ctx)
        check_body(s.body, ctx)
        if s.orelse:
            check_body(s.orelse, ctx)
        return
    if isinstance(s, ast.Assert):
        check_expr(s.test, ctx)
        if s.msg is not None:
            check_expr(s.msg, ctx)
        return
    if isinstance(s, ast.Match):
        check_expr(s.subject, ctx)
        check_pattern_list([c.pattern for c in s.cases], s, ctx)
        check_match_cases(s.cases, ctx)
        return
    if isinstance(s, ast.ClassDef):
        check_class_decl(s, ctx.gamma, ctx.q)
        return
    raise AssertionError(f"unexpected statement: {type(s).__name__}")


def check_match_cases(cases: list[ast.match_case], ctx: ModuleContext) -> None:
    for case in cases:
        check_body(
            case.body, override_var(ctx, {x: Status.TT for x in binds(case.pattern)})
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
        result = unary_type(name, operand, ctx)
        if result is None:
            raise IllFormedModule(e, reasons.NoUnarySignature(name, render(operand)))
        return result
    if isinstance(e, ast.BoolOp):
        operands = [check_expr(v, ctx) for v in e.values]
        return (
            Primitive.BOOL
            if all(t is not None and subtype(t, Primitive.BOOL, ctx) for t in operands)
            else None
        )
    if isinstance(e, ast.Compare):
        check_exprs(e.comparators, ctx)
        if len(e.ops) != 1:
            check_expr(e.left, ctx)
            return None
        return binary(BINARY_NAMES[type(e.ops[0])], e.left, e.comparators[0], e, ctx)
    if isinstance(e, ast.IfExp):
        check_expr(e.test, ctx)
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
        check_expr(e.value, ctx)
        return None
    if isinstance(e, ast.Subscript):
        check_expr(e.value, ctx)
        check_expr(e.slice, ctx)
        return None
    if isinstance(e, (ast.List, ast.Tuple)):
        check_exprs(e.elts, ctx)
        return None
    if isinstance(e, ast.Dict):
        check_exprs([k for k in e.keys if k is not None], ctx)
        check_exprs(e.values, ctx)
        return None
    if isinstance(e, ast.ListComp):
        check_comprehension([e.elt], e.generators, ctx)
        return None
    if isinstance(e, ast.DictComp):
        check_comprehension([e.key, e.value], e.generators, ctx)
        return None
    raise AssertionError(f"unexpected expression: {type(e).__name__}")


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
    """Check `e` against `expected`, where both types are known."""
    actual = check_expr(e, ctx)
    if expected is None or actual is None:
        return
    if not subtype(actual, expected, ctx):
        raise IllFormedModule(e, reasons.TypeMismatch(render(expected), render(actual)))


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
    result = binary_type(op, s, t, ctx)
    if result is None:
        raise IllFormedModule(e, reasons.NoBinarySignature(op, render(s), render(t)))
    return result


def check_comprehension(
    elts: list[ast.expr], generators: list[ast.comprehension], ctx: ModuleContext
) -> None:
    check_quals(generators, ctx)
    bound = binds_quals(generators)
    check_exprs(elts, override_var(ctx, {n: Status.TT for n in bound}))
    captured = captures_e_list(elts) & bound
    if captured:
        node = generators[0].target
        raise IllFormedModule(node, reasons.CapturedGeneratorVariable(min(captured)))


def check_quals(generators: list[ast.comprehension], ctx: ModuleContext) -> None:
    if len(generators) == 0:
        return
    g = generators[0]
    check_expr(g.iter, ctx)
    targets = names_in_target(g.target)
    captured = targets & (captures_e_list(g.ifs) | captures_quals(generators[1:]))
    if captured:
        raise IllFormedModule(
            g.target, reasons.CapturedGeneratorVariable(min(captured))
        )
    ctx_ = override_var(ctx, {n: Status.TT for n in targets})
    check_exprs(g.ifs, ctx_)
    check_quals(generators[1:], ctx_)


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
