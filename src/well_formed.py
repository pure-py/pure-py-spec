from __future__ import annotations

import ast
from typing import Optional

import reasons
from reasons import IllFormedModule
from contexts import (ClassEntry, Context, ContextEntry, ModuleContext, ModuleLoaded, ModuleStub,
                      ResultTy, Status, ASSIGNS_EMPTY, RETURNS, Assigns,
                      Returns, VarContext, class_of, extend_context, fields, merge_results,
                      module_of, override_gamma, override_results, override_var, var_status)
from aux import (BlockElement, assigns_block, assigns_elements, binds, captures_e, captures_element,
                 binds_seq, elements_of_block, find_first_reassigning, names_in_target, own_fields)
from patterns import dict_key, is_catch_all, subsumes

def class_entry_for(node: ast.ClassDef, q: str, context: Context) -> ClassEntry:
    base = node.bases[0].id if node.bases and isinstance(node.bases[0], ast.Name) else None
    return ClassEntry(context=context, name=f'{q}.{node.name}', own_fields=tuple(own_fields(node)), base=base)

def result_type(node: ast.stmt) -> ResultTy:
    if isinstance(node, ast.Pass):
        return ASSIGNS_EMPTY
    if isinstance(node, ast.Assign):
        return Assigns({t.id: Status.TT for t in node.targets if isinstance(t, ast.Name)})
    if isinstance(node, ast.Expr):
        return ASSIGNS_EMPTY
    if isinstance(node, ast.Assert):
        return ASSIGNS_EMPTY
    if isinstance(node, ast.Return):
        return RETURNS
    if isinstance(node, ast.FunctionDef):
        return Assigns({node.name: Status.TT})
    if isinstance(node, ast.If):
        return merge_results([result_type_of_block(node.body),
                              result_type_of_block(node.orelse) if node.orelse else ASSIGNS_EMPTY])
    if isinstance(node, ast.Match):
        branches = [override_results(Assigns({x: Status.TT for x in binds(case.pattern)}), result_type_of_block(case.body)) for case in node.cases]
        if not is_catch_all(node.cases[-1].pattern):
            branches.append(ASSIGNS_EMPTY)
        return merge_results(branches)
    if isinstance(node, ast.ClassDef):
        return ASSIGNS_EMPTY
    raise AssertionError(f'unexpected statement: {type(node).__name__}')

def result_type_of_block(block: list[ast.stmt]) -> ResultTy:
    if len(block) == 1:
        return result_type(block[0])
    return override_results(result_type(block[0]), result_type_of_block(block[1:]))

def check_block(block: list[ast.stmt], ctx: ModuleContext, module_body: bool = False) -> ModuleContext:
    return check_elements(elements_of_block(block), ctx, module_body)

def check_elements(items: list[BlockElement], ctx: ModuleContext, module_body: bool = False) -> ModuleContext:
    if len(items) == 0:
        return ctx
    head = items[0]
    check_element(head, ctx, module_body)
    if len(items) == 1:
        return next_ctx_after(head, ctx)
    tail = items[1:]
    if isinstance(block_element_result_type(head), Returns):
        first_unreachable = tail[0]
        node: ast.AST = first_unreachable[0] if isinstance(first_unreachable, list) else first_unreachable
        raise IllFormedModule(node, reasons.UnreachableStatement())
    reassigned = captures_element(head) & assigns_elements(tail)
    if reassigned:
        name = sorted(reassigned)[0]
        ra_node = find_first_reassigning(tail, reassigned)
        assert ra_node is not None
        raise IllFormedModule(ra_node, reasons.CapturedReassignment(name))
    return check_elements(tail, next_ctx_after(head, ctx), module_body)

def next_ctx_after(head: BlockElement, ctx: ModuleContext) -> ModuleContext:
    head_result = block_element_result_type(head)
    delta = head_result.delta if isinstance(head_result, Assigns) else {}
    next_ctx = override_var(ctx, delta)
    if isinstance(head, ast.ClassDef):
        next_ctx = override_gamma(next_ctx, {head.name: class_entry_for(head, ctx.q, ctx.gamma)})
    return next_ctx

def block_element_result_type(item: BlockElement) -> ResultTy:
    if isinstance(item, list):
        return Assigns({d.name: Status.TT for d in item})
    return result_type(item)

def check_element(item: BlockElement, ctx: ModuleContext, module_body: bool = False) -> None:
    if isinstance(item, list):
        check_mutual_region(item, ctx)
    else:
        check_stmt(item, ctx, module_body)

def check_mutual_region(defs: list[ast.FunctionDef], ctx: ModuleContext) -> None:
    check_distinct_names(defs, set())
    check_bodies(defs, ctx)

def check_bodies(defs: list[ast.FunctionDef], ctx: ModuleContext) -> None:
    f_names = {d.name: Status.TT for d in defs}
    for d in defs:
        params = {a.arg for a in d.args.args}
        locals_ = assigns_block(d.body) - params
        delta = f_names | {p: Status.TT for p in params} | {x: Status.FF for x in locals_}
        body_ctx = override_var(ctx, delta)
        check_block(d.body, body_ctx)

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

def entry_of(e: ast.expr, ctx: ModuleContext) -> Optional[ContextEntry]:
    if isinstance(e, ast.Name):
        return ctx.gamma.get(e.id)
    if isinstance(e, ast.Attribute):
        parent = entry_of(e.value, ctx)
        if isinstance(parent, ModuleLoaded):
            return parent.members.get(e.attr)
        return None
    return None

def check_stmt(s: ast.stmt, ctx: ModuleContext, module_body: bool = False) -> None:
    if isinstance(s, ast.Pass):
        return
    if isinstance(s, ast.Assign):
        check_expr(s.value, ctx)
        check_assign_targets(s.targets, captures_e(s.value))
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
        check_block(s.body, ctx)
        if s.orelse:
            check_block(s.orelse, ctx)
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
        if not module_body:
            raise IllFormedModule(s, reasons.NonTopLevelClass())
        check_class_decl(s, ctx.gamma, ctx.q)
        return
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def check_match_cases(cases: list[ast.match_case], ctx: ModuleContext) -> None:
    for case in cases:
        check_block(case.body, override_var(ctx, {x: Status.TT for x in binds(case.pattern)}))

def check_expr(e: ast.expr, ctx: ModuleContext) -> None:
    if isinstance(e, ast.Name):
        if var_status(ctx, e.id) != Status.TT:
            if module_of(ctx, e.id) is not None:
                raise IllFormedModule(e, reasons.ModuleAsValue(e.id))
            if class_of(ctx, e.id) is not None:
                raise IllFormedModule(e, reasons.ClassAsValue(e.id))
            raise IllFormedModule(e, reasons.UnassignedVariable(e.id))
        return
    if isinstance(e, ast.Constant):
        return
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        check_expr(e.body, override_var(ctx, {p: Status.TT for p in params}))
        return
    if isinstance(e, ast.Call):
        sig = names_class(e.func, ctx)
        if sig is not None:
            c_name, fields = sig
            n, m = len(e.args), len(e.keywords)
            if n + m != len(fields):
                raise IllFormedModule(e, reasons.ConstructorArityMismatch(c_name, len(fields), n + m))
            if {k.arg for k in e.keywords} != set(fields[n:]):
                raise IllFormedModule(e, reasons.UnknownConstructorKeyword(c_name, tuple(sorted(set(fields[n:])))))
            check_exprs(e.args, ctx)
            check_exprs([k.value for k in e.keywords], ctx)
            return
        check_expr(e.func, ctx)
        check_exprs(e.args, ctx)
        return
    if isinstance(e, ast.BinOp):
        check_expr(e.left, ctx)
        check_expr(e.right, ctx)
        return
    if isinstance(e, ast.UnaryOp):
        check_expr(e.operand, ctx)
        return
    if isinstance(e, ast.BoolOp):
        check_exprs(e.values, ctx)
        return
    if isinstance(e, ast.Compare):
        check_expr(e.left, ctx)
        check_exprs(e.comparators, ctx)
        return
    if isinstance(e, ast.IfExp):
        check_expr(e.test, ctx)
        check_expr(e.body, ctx)
        check_expr(e.orelse, ctx)
        return
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
            return
        if isinstance(parent, ModuleStub):
            raise IllFormedModule(e, reasons.SubmoduleNotImported(parent.q))
        check_expr(e.value, ctx)
        return
    if isinstance(e, ast.Subscript):
        check_expr(e.value, ctx)
        check_expr(e.slice, ctx)
        return
    if isinstance(e, (ast.List, ast.Tuple)):
        check_exprs(e.elts, ctx)
        return
    if isinstance(e, ast.Dict):
        check_exprs([k for k in e.keys if k is not None], ctx)
        check_exprs(e.values, ctx)
        return
    if isinstance(e, ast.ListComp):
        check_comprehension([e.elt], e.generators, ctx)
        return
    if isinstance(e, ast.DictComp):
        check_comprehension([e.key, e.value], e.generators, ctx)
        return
    raise AssertionError(f'unexpected expression: {type(e).__name__}')

def check_comprehension(elts: list[ast.expr], generators: list[ast.comprehension], ctx: ModuleContext) -> None:
    if len(generators) == 0:
        check_exprs(elts, ctx)
        return
    g = generators[0]
    check_expr(g.iter, ctx)
    ctx_ = override_var(ctx, {n: Status.TT for n in names_in_target(g.target)})
    check_exprs(g.ifs, ctx_)
    check_comprehension(elts, generators[1:], ctx_)

def check_exprs(es: list[ast.expr], ctx: ModuleContext) -> None:
    if len(es) == 0:
        return
    check_expr(es[0], ctx)
    check_exprs(es[1:], ctx)

def qualified_name(e: ast.expr) -> str:
    if isinstance(e, ast.Name):
        return e.id
    assert isinstance(e, ast.Attribute)
    return qualified_name(e.value) + '.' + e.attr

def names_class(head: ast.expr, ctx: ModuleContext) -> Optional[tuple[str, tuple[str, ...]]]:
    if isinstance(head, ast.Name):
        entry = class_of(ctx, head.id)
        return (head.id, fields(entry)) if entry is not None else None
    if isinstance(head, ast.Attribute):
        parent = entry_of(head.value, ctx)
        if not isinstance(parent, ModuleLoaded):
            return None
        member = parent.members.get(head.attr)
        if not isinstance(member, ClassEntry):
            return None
        return head.attr, fields(member)
    return None

def check_pattern(p: ast.pattern, ctx: ModuleContext) -> None:
    if isinstance(p, ast.MatchClass):
        sig = names_class(p.cls, ctx)
        if sig is None:
            raise IllFormedModule(p, reasons.UnknownClassInPattern(qualified_name(p.cls) if isinstance(p.cls, (ast.Name, ast.Attribute)) else ast.unparse(p.cls)))
        c_name, fields = sig
        n, m = len(p.patterns), len(p.kwd_patterns)
        if n + m != len(fields):
            raise IllFormedModule(p, reasons.PatternArityMismatch(c_name, len(fields), n + m))
        remaining = set(fields[n:])
        kwds = list(p.kwd_attrs)
        if len(kwds) != len(set(kwds)):
            raise IllFormedModule(p, reasons.DuplicatePatternKeyword(c_name))
        if set(kwds) != remaining:
            raise IllFormedModule(p, reasons.UnknownFieldInPattern(c_name, tuple(sorted(remaining))))
        for sub in list(p.patterns) + list(p.kwd_patterns):
            check_pattern(sub, ctx)
        return
    if isinstance(p, ast.MatchSequence):
        for sub in p.patterns:
            check_pattern(sub, ctx)
        return
    if isinstance(p, ast.MatchMapping):
        keys = [dict_key(key) for key in p.keys]
        duplicate = next((k for i, k in enumerate(keys) if k in keys[:i]), None)
        if duplicate is not None:
            raise IllFormedModule(p, reasons.DuplicateDictKey(duplicate))
        for sub in p.patterns:
            check_pattern(sub, ctx)
        return
    if isinstance(p, ast.MatchAs) and p.pattern is not None:
        check_pattern(p.pattern, ctx)
        return

def check_pattern_list(patterns: list[ast.pattern], node: ast.AST, ctx: ModuleContext) -> None:
    for i, p in enumerate(patterns):
        check_pattern(p, ctx)
        vars_ = binds_seq(p)
        if len(vars_) != len(set(vars_)):
            raise IllFormedModule(node, reasons.NonlinearPattern(i + 1))
        for j in range(i):
            if subsumes(p, patterns[j]):
                raise IllFormedModule(node, reasons.UnreachableCase(i + 1, j + 1))

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
    if not isinstance(entry, ClassEntry) or entry.name.rsplit('.', 1)[0] != q:
        raise IllFormedModule(node, reasons.UnknownBaseClass(base.id))
    clash = set(names) & set(fields(entry))
    if len(clash) > 0:
        raise IllFormedModule(node, reasons.InheritedFieldClash(sorted(clash)[0], base.id))
