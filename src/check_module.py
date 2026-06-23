import ast
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Union

import reasons
from reasons import Reason

class IllFormed(Exception):
    exit_code: int   # overridden by subclass
    msg: str


class IllFormedModule(IllFormed):
    exit_code = 3
    def __init__(self, node: ast.AST, reason: Reason):
        self.line: Optional[int] = getattr(node, 'lineno', None)
        self.col: Optional[int] = getattr(node, 'col_offset', None)
        self.reason: Reason = reason
        self.msg = reason.message()
        self.module: Optional[str] = None
        super().__init__(self.msg)


class Status(Enum):
    TT = auto()
    FF = auto()


BlockElement = Union[ast.stmt, list[ast.FunctionDef]]   # statement or grouped mutual region


@dataclass(frozen=True)
class ClassEntry:
    fields: tuple[str, ...]
    base: Optional[str]


@dataclass(frozen=True)
class ModuleRef:
    q: str


ContextEntry = Union[Status, ModuleRef, ClassEntry]
VarContext = dict[str, Status]           # Δ (assignment context: var-only)
ClassContext = dict[str, ClassEntry]     # syntactic subset of Γ for cross-module lookup


@dataclass(frozen=True)
class Context:
    gamma: dict[str, ContextEntry]
    M: dict[str, ast.Module] = field(default_factory=dict)
    q: str = ''


def extend_gamma(ctx: 'Context', delta: dict[str, ContextEntry]) -> 'Context':
    return Context(gamma={**ctx.gamma, **delta}, M=ctx.M, q=ctx.q)

def extend_var(ctx: 'Context', delta: VarContext) -> 'Context':
    return extend_gamma(ctx, dict(delta))

def class_entry_for(node: ast.ClassDef) -> 'ClassEntry':
    base = node.bases[0].id if node.bases and isinstance(node.bases[0], ast.Name) else None
    return ClassEntry(fields=tuple(class_field_names(node)), base=base)

def var_status(ctx: 'Context', x: str) -> Optional[Status]:
    v = ctx.gamma.get(x)
    return v if isinstance(v, Status) else None

def class_of(ctx: 'Context', c: str) -> Optional[ClassEntry]:
    v = ctx.gamma.get(c)
    return v if isinstance(v, ClassEntry) else None

def module_of(ctx: 'Context', x: str) -> Optional[ModuleRef]:
    v = ctx.gamma.get(x)
    return v if isinstance(v, ModuleRef) else None

def gamma_classes(ctx: 'Context') -> ClassContext:
    return {k: v for k, v in ctx.gamma.items() if isinstance(v, ClassEntry)}


@dataclass(frozen=True)
class TyReturns:
    pass

@dataclass(frozen=True)
class TyAssigns:
    delta: VarContext = field(default_factory=dict)


ResultTy = Union[TyReturns, TyAssigns]

TY_RETURNS = TyReturns()
TY_ASSIGNS = TyAssigns()
BUILTINS: VarContext = {'print': Status.TT, 'type': Status.TT, 'range': Status.TT, 'len': Status.TT}

def empty_context() -> VarContext:
    return {}

def extend(var_ctx: VarContext, delta: VarContext) -> VarContext:
    new = dict(var_ctx)
    new.update(delta)
    return new

def meet(a: Status, b: Status) -> Status:
    if a == Status.TT and b == Status.TT:
        return Status.TT
    return Status.FF

def merge_delta(d1: VarContext, d2: VarContext) -> VarContext:
    return {k: meet(d1[k], d2[k]) if k in d1 and k in d2 else Status.FF
            for k in set(d1.keys()) | set(d2.keys())}

def merge_results(rs: list[ResultTy]) -> ResultTy:
    assigns_branches = [r for r in rs if isinstance(r, TyAssigns)]
    if len(assigns_branches) == 0:
        return TY_RETURNS
    delta = assigns_branches[0].delta
    return TyAssigns(fold_merge(delta, assigns_branches[1:]))

def fold_merge(acc: VarContext, branches: list[TyAssigns]) -> VarContext:
    if len(branches) == 0:
        return acc
    return fold_merge(merge_delta(acc, branches[0].delta), branches[1:])

def runion_delta(d1: VarContext, d2: VarContext) -> VarContext:
    return {**d1, **d2}

def runion_results(r1: ResultTy, r2: ResultTy) -> ResultTy:
    if isinstance(r1, TyReturns):
        return r1
    if isinstance(r2, TyReturns):
        return r2
    return TyAssigns(runion_delta(r1.delta, r2.delta))

def result_type(node: ast.stmt) -> ResultTy:
    if isinstance(node, ast.Pass):
        return TY_ASSIGNS
    if isinstance(node, ast.Assign):
        return TyAssigns({t.id: Status.TT for t in node.targets if isinstance(t, ast.Name)})
    if isinstance(node, ast.Expr):
        return TY_ASSIGNS
    if isinstance(node, ast.Assert):
        return TY_ASSIGNS
    if isinstance(node, ast.Return):
        return TY_RETURNS
    if isinstance(node, ast.FunctionDef):
        return TyAssigns({node.name: Status.TT})
    if isinstance(node, ast.Import):
        return TyAssigns({node.names[0].name.split('.')[0]: Status.TT})
    if isinstance(node, ast.ImportFrom):
        return TyAssigns({a.name: Status.TT for a in node.names})
    if isinstance(node, ast.If):
        branches = [result_type_of_block(node.body)]
        if node.orelse:
            branches.append(result_type_of_block(node.orelse))
        else:
            branches.append(TY_ASSIGNS)
        return merge_results(branches)
    if isinstance(node, ast.Match):
        branches = [runion_results(TyAssigns({x: Status.TT for x in binds(case.pattern)}), result_type_of_block(case.body)) for case in node.cases]
        if not is_catch_all(node.cases[-1].pattern):
            branches.append(TY_ASSIGNS)
        return merge_results(branches)
    if isinstance(node, ast.ClassDef):
        return TY_ASSIGNS
    raise AssertionError(f'unexpected statement: {type(node).__name__}')

def result_type_of_block(block: list[ast.stmt]) -> ResultTy:
    if len(block) == 1:
        return result_type(block[0])
    return runion_results(result_type(block[0]), result_type_of_block(block[1:]))

def check_block(block: list[ast.stmt], ctx: Context) -> Context:
    return check_elements(elements_of_block(block), ctx)

def check_elements(items: list[BlockElement], ctx: Context) -> Context:
    if len(items) == 0:
        return ctx
    head = items[0]
    check_element(head, ctx)
    if len(items) == 1:
        return next_ctx_after(head, ctx)
    tail = items[1:]
    if isinstance(block_element_result_type(head), TyReturns):
        first_unreachable = tail[0]
        node: ast.AST = first_unreachable[0] if isinstance(first_unreachable, list) else first_unreachable
        raise IllFormedModule(node, reasons.UnreachableStatement())
    reassigned = captures_element(head) & assigns_elements(tail)
    if reassigned:
        name = sorted(reassigned)[0]
        ra_node = find_first_reassigning(tail, reassigned)
        assert ra_node is not None
        raise IllFormedModule(ra_node, reasons.CapturedReassignment(name))
    return check_elements(tail, next_ctx_after(head, ctx))

def next_ctx_after(head: BlockElement, ctx: Context) -> Context:
    head_result = block_element_result_type(head)
    delta = head_result.delta if isinstance(head_result, TyAssigns) else {}
    next_ctx = extend_var(ctx, delta)
    if isinstance(head, ast.ClassDef):
        next_ctx = extend_gamma(next_ctx, {head.name: class_entry_for(head)})
    if isinstance(head, ast.Import):
        head_seg = head.names[0].name.split('.')[0]
        next_ctx = extend_gamma(next_ctx, {head_seg: ModuleRef(head_seg)})
    return next_ctx

def block_element_result_type(item: BlockElement) -> ResultTy:
    if isinstance(item, list):
        return TyAssigns({d.name: Status.TT for d in item})
    return result_type(item)

def elements_of_block(block: list[ast.stmt]) -> list[BlockElement]:
    if len(block) == 0:
        return []
    head = block[0]
    rest = block[1:]
    if isinstance(head, ast.FunctionDef):
        return extend_region([head], rest)
    return [head] + elements_of_block(rest)

def extend_region(region: list[ast.FunctionDef], rest: list[ast.stmt]) -> list[BlockElement]:
    if len(rest) == 0:
        return [region]
    head = rest[0]
    if isinstance(head, ast.FunctionDef):
        return extend_region(region + [head], rest[1:])
    return [region] + elements_of_block(rest)

def check_element(item: BlockElement, ctx: Context) -> None:
    if isinstance(item, list):
        check_mutual_region(item, ctx)
    else:
        check_stmt(item, ctx)

def check_mutual_region(defs: list[ast.FunctionDef], ctx: Context) -> None:
    check_distinct_names(defs, set())
    check_bodies(defs, ctx)

def check_bodies(defs: list[ast.FunctionDef], ctx: Context) -> None:
    f_names = {d.name: Status.TT for d in defs}
    for d in defs:
        params = {a.arg for a in d.args.args}
        locals_ = assigns_block(d.body) - params
        delta = f_names | {p: Status.TT for p in params} | {x: Status.FF for x in locals_}
        body_ctx = extend_var(ctx, delta)
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

def check_import(s: ast.stmt, q: str, ctx: Context) -> None:
    if q == ctx.q:
        raise IllFormedModule(s, reasons.SelfImport(q))
    if q not in ctx.M:
        raise IllFormedModule(s, reasons.UnknownModule(q))
    check_module(ctx.M[q], ctx.M, q)

def imports(s: ast.stmt, q: str, names: list[str], ctx: Context) -> None:
    body = ctx.M[q].body
    if len(body) == 0:
        return
    members = module_members(body, ctx.M, q)
    unknown = next((x for x in names if x not in members), None)
    if unknown is not None:
        raise IllFormedModule(s, reasons.UnknownMember(unknown, q))

def module_members(body: list[ast.stmt], M: dict[str, ast.Module], q: str) -> set[str]:
    submodules = {name[len(q) + 1:].split('.')[0] for name in M if name.startswith(f'{q}.')}
    return assigns_block(body) | {s.name for s in body if isinstance(s, ast.ClassDef)} | set(BUILTINS.keys()) | {'__name__'} | submodules

def names_module(e: ast.expr, ctx: Context) -> Optional[str]:
    if isinstance(e, ast.Name):
        m = module_of(ctx, e.id)
        return m.q if m is not None and m.q in ctx.M else None
    if isinstance(e, ast.Attribute):
        parent = names_module(e.value, ctx)
        full = f'{parent}.{e.attr}' if parent is not None else None
        return full if full is not None and full in ctx.M else None
    return None

def check_stmt(s: ast.stmt, ctx: Context) -> None:
    if isinstance(s, ast.Pass):
        return
    if isinstance(s, ast.Assign):
        check_expr(s.value, ctx)
        check_assign_targets(s.targets, captures(s.value))
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
    if isinstance(s, ast.Import):
        check_import(s, s.names[0].name, ctx)
        return
    if isinstance(s, ast.ImportFrom):
        if len(s.names) == 0:
            raise IllFormedModule(s, reasons.EmptyFromImport())
        assert s.module is not None
        check_import(s, s.module, ctx)
        imports(s, s.module, [a.name for a in s.names], ctx)
        return
    if isinstance(s, ast.Match):
        check_expr(s.subject, ctx)
        check_pattern_list([c.pattern for c in s.cases], s, ctx)
        check_match_cases(s.cases, ctx)
        return
    if isinstance(s, ast.ClassDef):
        check_class_decl(s, gamma_classes(ctx))
        return
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def check_match_cases(cases: list[ast.match_case], ctx: Context) -> None:
    for case in cases:
        check_block(case.body, extend_var(ctx, {x: Status.TT for x in binds(case.pattern)}))

def check_expr(e: ast.expr, ctx: Context) -> None:
    if isinstance(e, ast.Name):
        if var_status(ctx, e.id) != Status.TT:
            raise IllFormedModule(e, reasons.UnassignedVariable(e.id))
        return
    if isinstance(e, ast.Constant):
        return
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        check_expr(e.body, extend_var(ctx, {p: Status.TT for p in params}))
        return
    if isinstance(e, ast.Call):
        sig = names_class(e.func, ctx)
        if sig is not None:
            c_name, fields = sig
            if len(e.args) != len(fields):
                raise IllFormedModule(e, reasons.ConstructorArityMismatch(c_name, len(fields), len(e.args)))
            check_exprs(e.args, ctx)
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
        mod = names_module(e.value, ctx)
        if mod is not None:
            body = ctx.M[mod].body
            if len(body) > 0 and e.attr not in module_members(body, ctx.M, mod):
                raise IllFormedModule(e, reasons.UnknownMember(e.attr, mod))
            return
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
        check_comprehension(e.elt, e.generators, ctx)
        return
    raise AssertionError(f'unexpected expression: {type(e).__name__}')

def check_comprehension(elt: ast.expr, generators: list[ast.comprehension], ctx: Context) -> None:
    if len(generators) == 0:
        check_expr(elt, ctx)
        return
    g = generators[0]
    check_expr(g.iter, ctx)
    ctx_ = extend_var(ctx, {n: Status.TT for n in names_in_target(g.target)})
    check_exprs(g.ifs, ctx_)
    check_comprehension(elt, generators[1:], ctx_)

def check_exprs(es: list[ast.expr], ctx: Context) -> None:
    if len(es) == 0:
        return
    check_expr(es[0], ctx)
    check_exprs(es[1:], ctx)

def is_catch_all(p: ast.pattern) -> bool:
    return isinstance(p, ast.MatchAs) and p.pattern is None

def literal_value(pat: ast.MatchValue) -> object:
    v = pat.value
    if isinstance(v, ast.Constant):
        return v.value
    if isinstance(v, ast.UnaryOp) and isinstance(v.operand, ast.Constant):
        operand_value = v.operand.value
        assert isinstance(operand_value, (int, float))
        return -operand_value if isinstance(v.op, ast.USub) else operand_value
    raise AssertionError(f'unexpected MatchValue payload: {type(v).__name__}')

def subsumes(p: ast.pattern, q: ast.pattern) -> bool:
    if isinstance(q, ast.MatchAs) and q.pattern is not None:
        return subsumes(p, q.pattern)
    if isinstance(p, ast.MatchAs) and p.pattern is not None:
        return subsumes(p.pattern, q)
    if isinstance(q, ast.MatchAs) and q.pattern is None:
        return True
    if isinstance(p, ast.MatchValue) and isinstance(q, ast.MatchValue):
        return literal_value(p) == literal_value(q)
    if isinstance(p, ast.MatchSingleton) and isinstance(q, ast.MatchSingleton):
        return p.value is q.value
    if isinstance(p, ast.MatchSequence) and isinstance(q, ast.MatchSequence):
        if len(p.patterns) != len(q.patterns):
            return False
        return all((subsumes(pi, qi) for pi, qi in zip(p.patterns, q.patterns)))
    return False

def pattern_vars(p: ast.pattern) -> list[str]:
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return []
    if isinstance(p, ast.MatchAs):
        sub = pattern_vars(p.pattern) if p.pattern is not None else []
        return sub + ([p.name] if p.name else [])
    if isinstance(p, ast.MatchSequence):
        return [v for sub in p.patterns for v in pattern_vars(sub)]
    if isinstance(p, ast.MatchClass):
        return [v for sub in p.patterns for v in pattern_vars(sub)] + \
               [v for sub in p.kwd_patterns for v in pattern_vars(sub)]
    raise AssertionError(f'unexpected pattern: {type(p).__name__}')

def qualified_name(e: ast.expr) -> str:
    if isinstance(e, ast.Name):
        return e.id
    assert isinstance(e, ast.Attribute)
    return qualified_name(e.value) + '.' + e.attr

def names_class(head: ast.expr, ctx: Context) -> Optional[tuple[str, tuple[str, ...]]]:
    if isinstance(head, ast.Name):
        entry = class_of(ctx, head.id)
        return (head.id, fields_of(gamma_classes(ctx), head.id)) if entry is not None else None
    if isinstance(head, ast.Attribute) and isinstance(head.value, (ast.Name, ast.Attribute)):
        mod_path = qualified_name(head.value)
        root = mod_path.split('.')[0]
        if module_of(ctx, root) is None or mod_path not in ctx.M:
            return None
        mod_cls = check_module(ctx.M[mod_path], ctx.M, mod_path)
        if head.attr not in mod_cls:
            return None
        return head.attr, fields_of(mod_cls, head.attr)
    return None

def check_pattern(p: ast.pattern, ctx: Context) -> None:
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
    if isinstance(p, ast.MatchAs) and p.pattern is not None:
        check_pattern(p.pattern, ctx)
        return

def check_pattern_list(patterns: list[ast.pattern], node: ast.AST, ctx: Context) -> None:
    for i, p in enumerate(patterns):
        check_pattern(p, ctx)
        vars_ = pattern_vars(p)
        if len(vars_) != len(set(vars_)):
            raise IllFormedModule(node, reasons.NonlinearPattern(i + 1))
        for j in range(i):
            if subsumes(p, patterns[j]):
                raise IllFormedModule(node, reasons.UnreachableCase(i + 1, j + 1))

def binds(pattern: ast.pattern) -> set[str]:
    if isinstance(pattern, (ast.MatchValue, ast.MatchSingleton)):
        return set()
    if isinstance(pattern, ast.MatchAs):
        sub = binds(pattern.pattern) if pattern.pattern is not None else set()
        return sub | ({pattern.name} if pattern.name else set())
    if isinstance(pattern, ast.MatchSequence):
        return set().union(*(binds(p) for p in pattern.patterns))
    if isinstance(pattern, ast.MatchClass):
        return set().union(*(binds(p) for p in list(pattern.patterns) + list(pattern.kwd_patterns)))
    raise AssertionError(f'unexpected pattern: {type(pattern).__name__}')

def fv(e: ast.expr) -> set[str]:
    if isinstance(e, ast.Name):
        return {e.id}
    if isinstance(e, ast.Constant):
        return set()
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        return fv(e.body) - params
    if isinstance(e, ast.Call):
        return fv(e.func) | fv_list(e.args)
    if isinstance(e, ast.BinOp):
        return fv(e.left) | fv(e.right)
    if isinstance(e, ast.UnaryOp):
        return fv(e.operand)
    if isinstance(e, ast.BoolOp):
        return fv_list(e.values)
    if isinstance(e, ast.Compare):
        return fv(e.left) | fv_list(e.comparators)
    if isinstance(e, ast.IfExp):
        return fv(e.test) | fv(e.body) | fv(e.orelse)
    if isinstance(e, ast.Attribute):
        return fv(e.value)
    if isinstance(e, ast.Subscript):
        return fv(e.value) | fv(e.slice)
    if isinstance(e, (ast.List, ast.Tuple)):
        return fv_list(e.elts)
    if isinstance(e, ast.Dict):
        return fv_list([k for k in e.keys if k is not None]) | fv_list(e.values)
    if isinstance(e, ast.ListComp):
        return fv_comprehension(e.elt, e.generators)
    raise AssertionError(f'unexpected expression: {type(e).__name__}')

def fv_list(es: list[ast.expr]) -> set[str]:
    if len(es) == 0:
        return set()
    return fv(es[0]) | fv_list(es[1:])

def fv_comprehension(elt: ast.expr, generators: list[ast.comprehension]) -> set[str]:
    if len(generators) == 0:
        return fv(elt)
    g = generators[0]
    target_names = names_in_target(g.target)
    rest = fv_list(g.ifs) | fv_comprehension(elt, generators[1:])
    return fv(g.iter) | rest - target_names

def names_in_target(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple):
        return {n for t in target.elts for n in names_in_target(t)}
    return set()

def captures(e: ast.expr) -> set[str]:
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        return fv(e.body) - params
    if isinstance(e, ast.Name):
        return set()
    if isinstance(e, ast.Constant):
        return set()
    if isinstance(e, ast.Call):
        return captures(e.func) | captures_list(e.args)
    if isinstance(e, ast.BinOp):
        return captures(e.left) | captures(e.right)
    if isinstance(e, ast.UnaryOp):
        return captures(e.operand)
    if isinstance(e, ast.BoolOp):
        return captures_list(e.values)
    if isinstance(e, ast.Compare):
        return captures(e.left) | captures_list(e.comparators)
    if isinstance(e, ast.IfExp):
        return captures(e.test) | captures(e.body) | captures(e.orelse)
    if isinstance(e, ast.Attribute):
        return captures(e.value)
    if isinstance(e, ast.Subscript):
        return captures(e.value) | captures(e.slice)
    if isinstance(e, (ast.List, ast.Tuple)):
        return captures_list(e.elts)
    if isinstance(e, ast.Dict):
        return captures_list([k for k in e.keys if k is not None]) | captures_list(e.values)
    if isinstance(e, ast.ListComp):
        return captures_comprehension(e.elt, e.generators)
    raise AssertionError(f'unexpected expression: {type(e).__name__}')

def captures_list(es: list[ast.expr]) -> set[str]:
    if len(es) == 0:
        return set()
    return captures(es[0]) | captures_list(es[1:])

def captures_comprehension(elt: ast.expr, generators: list[ast.comprehension]) -> set[str]:
    if len(generators) == 0:
        return captures(elt)
    g = generators[0]
    target_names = names_in_target(g.target)
    rest = captures_list(g.ifs) | captures_comprehension(elt, generators[1:])
    return captures(g.iter) | rest - target_names

def fv_stmt(s: ast.stmt) -> set[str]:
    if isinstance(s, ast.Pass):
        return set()
    if isinstance(s, ast.Assign):
        return fv(s.value)
    if isinstance(s, ast.Expr):
        return fv(s.value)
    if isinstance(s, ast.Return):
        return fv(s.value) if s.value is not None else set()
    if isinstance(s, ast.Assert):
        result = fv(s.test)
        if s.msg is not None:
            result = result | fv(s.msg)
        return result
    if isinstance(s, ast.If):
        return fv(s.test) | fv_block(s.body) | fv_block(s.orelse)
    if isinstance(s, ast.Match):
        return fv(s.subject) | set().union(*(fv_block(case.body) - binds(case.pattern) for case in s.cases))
    if isinstance(s, ast.FunctionDef):
        params = {a.arg for a in s.args.args}
        return fv_block(s.body) - params - {s.name}
    if isinstance(s, (ast.Import, ast.ImportFrom)):
        return set()
    if isinstance(s, ast.ClassDef):
        return set()
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def fv_block(block: list[ast.stmt]) -> set[str]:
    if len(block) == 0:
        return set()
    return fv_stmt(block[0]) | fv_block(block[1:])

def assigns_stmt(s: ast.stmt) -> set[str]:
    if isinstance(s, (ast.Pass, ast.Expr, ast.Return, ast.Assert)):
        return set()
    if isinstance(s, ast.Assign):
        return {t.id for t in s.targets if isinstance(t, ast.Name)}
    if isinstance(s, ast.If):
        return assigns_block(s.body) | assigns_block(s.orelse)
    if isinstance(s, ast.Match):
        return set().union(*(binds(case.pattern) | assigns_block(case.body) for case in s.cases))
    if isinstance(s, ast.FunctionDef):
        return {s.name}
    if isinstance(s, ast.Import):
        return {s.names[0].name.split('.')[0]}
    if isinstance(s, ast.ImportFrom):
        return {a.name for a in s.names}
    if isinstance(s, ast.ClassDef):
        return set()
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def assigns_block(block: list[ast.stmt]) -> set[str]:
    if len(block) == 0:
        return set()
    return assigns_stmt(block[0]) | assigns_block(block[1:])

def captures_stmt(s: ast.stmt) -> set[str]:
    if isinstance(s, ast.Pass):
        return set()
    if isinstance(s, ast.Assign):
        return captures(s.value)
    if isinstance(s, ast.Expr):
        return captures(s.value)
    if isinstance(s, ast.Return):
        return captures(s.value) if s.value is not None else set()
    if isinstance(s, ast.Assert):
        result = captures(s.test)
        if s.msg is not None:
            result = result | captures(s.msg)
        return result
    if isinstance(s, ast.If):
        return captures(s.test) | captures_block(s.body) | captures_block(s.orelse)
    if isinstance(s, ast.Match):
        return captures(s.subject) | set().union(*(captures_block(case.body) - binds(case.pattern) for case in s.cases))
    if isinstance(s, ast.FunctionDef):
        return captures_region([s])
    if isinstance(s, (ast.Import, ast.ImportFrom)):
        return set()
    if isinstance(s, ast.ClassDef):
        return set()
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def captures_block(block: list[ast.stmt]) -> set[str]:
    if len(block) == 0:
        return set()
    return captures_stmt(block[0]) | captures_block(block[1:])

def captures_region(defs: list[ast.FunctionDef]) -> set[str]:
    f_names = {d.name for d in defs}
    return captures_region_bodies(defs) - f_names

def captures_region_bodies(defs: list[ast.FunctionDef]) -> set[str]:
    if len(defs) == 0:
        return set()
    d = defs[0]
    params = {a.arg for a in d.args.args}
    own = fv_block(d.body) - params - assigns_block(d.body)
    return own | captures_region_bodies(defs[1:])

def captures_element(item: BlockElement) -> set[str]:
    if isinstance(item, list):
        return captures_region(item)
    return captures_stmt(item)

def assigns_element(item: BlockElement) -> set[str]:
    if isinstance(item, list):
        return {d.name for d in item}
    return assigns_stmt(item)

def assigns_elements(items: list[BlockElement]) -> set[str]:
    if len(items) == 0:
        return set()
    return assigns_element(items[0]) | assigns_elements(items[1:])

def find_first_reassigning(items: list[BlockElement], names: set[str]) -> Optional[ast.AST]:
    if len(items) == 0:
        return None
    if assigns_element(items[0]) & names:
        return items[0][0] if isinstance(items[0], list) else items[0]
    return find_first_reassigning(items[1:], names)

def find_nested_import(stmts: list[ast.stmt], nested: bool = False) -> ast.AST | None:
    """Return the first import statement appearing in a non-top-level context.
    nested=True means stmts themselves are inside a non-top-level body."""
    for s in stmts:
        if nested and isinstance(s, (ast.Import, ast.ImportFrom)):
            return s
        if isinstance(s, ast.FunctionDef):
            r = find_nested_import(s.body, nested=True)
            if r is not None:
                return r
        if isinstance(s, ast.If):
            r = find_nested_import(s.body, nested=True) or find_nested_import(s.orelse, nested=True)
            if r is not None:
                return r
        if isinstance(s, ast.Match):
            results = (find_nested_import(case.body, nested=True) for case in s.cases)
            r = next((x for x in results if x is not None), None)
            if r is not None:
                return r
    return None

def class_field_names(node: ast.ClassDef) -> list[str]:
    return [t.target.id for t in node.body
            if isinstance(t, ast.AnnAssign) and isinstance(t.target, ast.Name)]

def has_cycle(graph: dict[str, set[str]]) -> list[str]:
    """DFS cycle detection. Returns a cycle (as a list of names) if one exists, else []."""
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

def fields_of(lambda_m: ClassContext, c: str) -> tuple[str, ...]:
    info = lambda_m[c]
    if info.base is None:
        return info.fields
    return fields_of(lambda_m, info.base) + info.fields

def check_class_decl(node: ast.ClassDef, lambda_m: ClassContext) -> None:
    names = class_field_names(node)
    dup = next((n for i, n in enumerate(names) if n in names[:i]), None)
    if dup is not None:
        raise IllFormedModule(node, reasons.DuplicateFieldName(dup, node.name))
    if len(node.bases) == 0:
        return
    base = node.bases[0]
    assert isinstance(base, ast.Name)
    if base.id not in lambda_m:
        raise IllFormedModule(node, reasons.UnknownBaseClass(base.id))
    clash = set(names) & set(fields_of(lambda_m, base.id))
    if len(clash) > 0:
        raise IllFormedModule(node, reasons.InheritedFieldClash(sorted(clash)[0], base.id))

def check_module(m: ast.Module, M: dict[str, ast.Module], q: str) -> ClassContext:
    try:
        return check_module_(m, M, q)
    except IllFormedModule as e:
        if e.module is None:
            e.module = q
        raise

def check_module_(m: ast.Module, M: dict[str, ast.Module], q: str) -> ClassContext:
    if len(m.body) == 0:
        return {}
    nested = find_nested_import(m.body)
    if nested is not None:
        raise IllFormedModule(nested, reasons.NestedImport())
    gamma: dict[str, ContextEntry] = {**BUILTINS, '__name__': Status.TT}
    final_ctx = check_block(m.body, Context(gamma=gamma, M=M, q=q))
    if isinstance(result_type_of_block(m.body), TyReturns):
        raise IllFormedModule(m.body[0], reasons.TopLevelReturn())
    return gamma_classes(final_ctx)

def module_result(m: ast.Module, M: dict[str, ast.Module], q: str) -> Optional[IllFormed]:
    try:
        check_module(m, M, q)
        return None
    except IllFormed as e:
        return e


PREDEFINED_MODULES = {'builtins', 'math', 'sys', 'typing', 'dataclasses'}

def check_file(filename: str) -> Optional[IllFormed]:
    source = open(filename).read()
    tree = ast.parse(source, filename=filename)
    q = filename.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    M: dict[str, ast.Module] = {p: ast.Module(body=[], type_ignores=[]) for p in PREDEFINED_MODULES}
    M[q] = tree
    return module_result(tree, M, q)

def format_result(result: Optional[IllFormed], filename: str) -> str:
    if result is None:
        return f'{filename}: ok'
    assert isinstance(result, IllFormedModule)
    return f'{filename}:{result.line}:{result.col}: {result.msg}'

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
