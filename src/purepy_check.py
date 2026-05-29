import ast
import sys
from dataclasses import dataclass, field
from typing import Optional, Union

ILL_FORMED = 3


@dataclass(frozen=True)
class Error:
    line: Optional[int]
    col: Optional[int]
    msg: str
    kind: int


Result = Optional[Error]


def ok() -> Result:
    return None

def ill_formed(node: ast.AST, msg: str) -> Result:
    return Error(getattr(node, 'lineno', None), getattr(node, 'col_offset', None), msg, ILL_FORMED)

def is_ok(result: Result) -> bool:
    return result is None
TT = 'tt'
FF = 'ff'

Status = str                          # "tt" or "ff"
Context = dict[str, Status]           # Γ, Δ
Item = Union[ast.stmt, list[ast.FunctionDef]]   # statement or grouped mutual region


@dataclass(frozen=True)
class TyReturns:
    pass

@dataclass(frozen=True)
class TyAssigns:
    delta: Context = field(default_factory=dict)


ResultTy = Union[TyReturns, TyAssigns]

TY_RETURNS = TyReturns()
TY_ASSIGNS = TyAssigns()
BUILTINS: Context = {'print': TT, 'type': TT, 'range': TT, 'len': TT}

def empty_context() -> Context:
    return {}

def extend(gamma: Context, delta: Context) -> Context:
    new = dict(gamma)
    new.update(delta)
    return new

def meet(a: Status, b: Status) -> Status:
    if a == TT and b == TT:
        return TT
    return FF

def merge_delta(d1: Context, d2: Context) -> Context:
    result = {}
    for k in set(d1.keys()) | set(d2.keys()):
        if k in d1 and k in d2:
            result[k] = meet(d1[k], d2[k])
        else:
            result[k] = FF
    return result

def merge_results(rs: list[ResultTy]) -> ResultTy:
    assigns_branches = [r for r in rs if isinstance(r, TyAssigns)]
    if not assigns_branches:
        return TY_RETURNS
    delta = assigns_branches[0].delta
    return TyAssigns(_fold_merge(delta, assigns_branches[1:]))

def _fold_merge(acc: Context, branches: list[TyAssigns]) -> Context:
    if not branches:
        return acc
    return _fold_merge(merge_delta(acc, branches[0].delta), branches[1:])

def runion_delta(d1: Context, d2: Context) -> Context:
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
        return TyAssigns({t.id: TT for t in node.targets if isinstance(t, ast.Name)})
    if isinstance(node, ast.Expr):
        return TY_ASSIGNS
    if isinstance(node, ast.Assert):
        return TY_ASSIGNS
    if isinstance(node, ast.Return):
        return TY_RETURNS
    if isinstance(node, ast.FunctionDef):
        return TyAssigns({node.name: TT})
    if isinstance(node, ast.Import):
        return TyAssigns({node.names[0].name.split('.')[0]: TT})
    if isinstance(node, ast.ImportFrom):
        return TyAssigns({a.name: TT for a in node.names})
    if isinstance(node, ast.If):
        branches = [result_type_of_block(node.body)]
        if node.orelse:
            branches.append(result_type_of_block(node.orelse))
        else:
            branches.append(TY_ASSIGNS)
        return merge_results(branches)
    if isinstance(node, ast.Match):
        branches = [runion_results(TyAssigns({x: TT for x in binds(case.pattern)}), result_type_of_block(case.body)) for case in node.cases]
        if not _is_catch_all(node.cases[-1].pattern):
            branches.append(TY_ASSIGNS)
        return merge_results(branches)
    raise AssertionError(f'unexpected statement: {type(node).__name__}')

def result_type_of_block(block: list[ast.stmt]) -> ResultTy:
    if len(block) == 1:
        return _result_type_of_item(block[0])
    return runion_results(_result_type_of_item(block[0]), result_type_of_block(block[1:]))

def _result_type_of_item(stmt: ast.stmt) -> ResultTy:
    return result_type(stmt)

def check_block(block: list[ast.stmt], gamma: Context) -> Result:
    items = items_of_block(block)
    return check_items(items, gamma)

def check_items(items: list[Item], gamma: Context) -> Result:
    if len(items) == 1:
        return check_item(items[0], gamma)
    head = items[0]
    tail = items[1:]
    err = check_item(head, gamma)
    if not is_ok(err):
        return err
    if isinstance(item_result_type(head), TyReturns):
        first_unreachable = tail[0]
        node: ast.AST = first_unreachable[0] if isinstance(first_unreachable, list) else first_unreachable
        return ill_formed(node, '[seq] unreachable statement')
    reassigned = captures_item(head) & assigns_items(tail)
    if reassigned:
        name = sorted(reassigned)[0]
        ra_node = find_first_reassigning(tail, reassigned)
        assert ra_node is not None
        return ill_formed(ra_node, f"[seq] '{name}' captured by previous statement, reassigned here")
    head_result = item_result_type(head)
    delta = head_result.delta if isinstance(head_result, TyAssigns) else {}
    return check_items(tail, extend(gamma, delta))

def item_result_type(item: Item) -> ResultTy:
    if isinstance(item, list):
        return TyAssigns({d.name: TT for d in item})
    return result_type(item)

def items_of_block(block: list[ast.stmt]) -> list[Item]:
    if not block:
        return []
    head = block[0]
    rest = block[1:]
    if isinstance(head, ast.FunctionDef):
        return _extend_region([head], rest)
    return [head] + items_of_block(rest)

def _extend_region(region: list[ast.FunctionDef], rest: list[ast.stmt]) -> list[Item]:
    if not rest:
        return [region]
    head = rest[0]
    if isinstance(head, ast.FunctionDef):
        return _extend_region(region + [head], rest[1:])
    return [region] + items_of_block(rest)

def check_item(item: Item, gamma: Context) -> Result:
    if isinstance(item, list):
        return check_mutual_region(item, gamma)
    return check_stmt(item, gamma)

def check_mutual_region(defs: list[ast.FunctionDef], gamma: Context) -> Result:
    err = check_distinct_names(defs, set())
    if not is_ok(err):
        return err
    return check_bodies(defs, gamma)

def check_bodies(defs: list[ast.FunctionDef], gamma: Context) -> Result:
    f_names = {d.name: TT for d in defs}
    return _check_bodies(defs, gamma, f_names)

def _check_bodies(defs: list[ast.FunctionDef], gamma: Context, f_names: Context) -> Result:
    if not defs:
        return ok()
    d = defs[0]
    params = {a.arg for a in d.args.args}
    locals_ = assigns_block(d.body) - params
    body_gamma = extend(extend(extend(gamma, f_names), {p: TT for p in params}), {x: FF for x in locals_})
    err = check_block(d.body, body_gamma)
    if not is_ok(err):
        return err
    return _check_bodies(defs[1:], gamma, f_names)

def check_assign_targets(targets: list[ast.expr], captured: set[str]) -> Result:
    if not targets:
        return ok()
    t = targets[0]
    if isinstance(t, ast.Name) and t.id in captured:
        return ill_formed(t, f"[assign] '{t.id}' captured by right-hand side")
    return check_assign_targets(targets[1:], captured)

def check_distinct_names(defs: list[ast.FunctionDef], seen: set[str]) -> Result:
    if not defs:
        return ok()
    head = defs[0]
    if head.name in seen:
        return ill_formed(head, f"[mutual] duplicate name '{head.name}' in mutual region")
    return check_distinct_names(defs[1:], seen | {head.name})

def check_stmt(s: ast.stmt, gamma: Context) -> Result:
    if isinstance(s, ast.Pass):
        return ok()
    if isinstance(s, ast.Assign):
        err = check_expr(s.value, gamma)
        if not is_ok(err):
            return err
        captured = captures(s.value)
        return check_assign_targets(s.targets, captured)
    if isinstance(s, ast.Expr):
        return check_expr(s.value, gamma)
    if isinstance(s, ast.Return):
        if s.value is not None:
            return check_expr(s.value, gamma)
        return ok()
    if isinstance(s, ast.If):
        err = check_expr(s.test, gamma)
        if not is_ok(err):
            return err
        err = check_block(s.body, gamma)
        if not is_ok(err):
            return err
        if s.orelse:
            return check_block(s.orelse, gamma)
        return ok()
    if isinstance(s, ast.Assert):
        err = check_expr(s.test, gamma)
        if not is_ok(err):
            return err
        if s.msg is not None:
            return check_expr(s.msg, gamma)
        return ok()
    if isinstance(s, (ast.Import, ast.ImportFrom)):
        return ok()
    if isinstance(s, ast.Match):
        err = check_expr(s.subject, gamma)
        if not is_ok(err):
            return err
        patterns = [c.pattern for c in s.cases]
        err = check_pattern_list(patterns, s)
        if not is_ok(err):
            return err
        return _check_match_cases(s.cases, gamma)
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def _check_match_cases(cases: list[ast.match_case], gamma: Context) -> Result:
    for case in cases:
        case_gamma = extend(gamma, {x: TT for x in binds(case.pattern)})
        err = check_block(case.body, case_gamma)
        if not is_ok(err):
            return err
    return ok()

def check_expr(e: ast.expr, gamma: Context) -> Result:
    if isinstance(e, ast.Name):
        if gamma.get(e.id) != TT:
            return ill_formed(e, f"[var] '{e.id}' is not definitely assigned")
        return ok()
    if isinstance(e, ast.Constant):
        return ok()
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        gamma_ = extend(gamma, {p: TT for p in params})
        return check_expr(e.body, gamma_)
    if isinstance(e, ast.Call):
        err = check_expr(e.func, gamma)
        if not is_ok(err):
            return err
        return check_exprs(e.args, gamma)
    if isinstance(e, ast.BinOp):
        err = check_expr(e.left, gamma)
        if not is_ok(err):
            return err
        return check_expr(e.right, gamma)
    if isinstance(e, ast.UnaryOp):
        return check_expr(e.operand, gamma)
    if isinstance(e, ast.BoolOp):
        return check_exprs(e.values, gamma)
    if isinstance(e, ast.Compare):
        err = check_expr(e.left, gamma)
        if not is_ok(err):
            return err
        return check_exprs(e.comparators, gamma)
    if isinstance(e, ast.IfExp):
        err = check_expr(e.test, gamma)
        if not is_ok(err):
            return err
        err = check_expr(e.body, gamma)
        if not is_ok(err):
            return err
        return check_expr(e.orelse, gamma)
    if isinstance(e, ast.Attribute):
        return check_expr(e.value, gamma)
    if isinstance(e, ast.Subscript):
        err = check_expr(e.value, gamma)
        if not is_ok(err):
            return err
        return check_expr(e.slice, gamma)
    if isinstance(e, (ast.List, ast.Tuple)):
        return check_exprs(e.elts, gamma)
    if isinstance(e, ast.Dict):
        err = check_exprs([k for k in e.keys if k is not None], gamma)
        if not is_ok(err):
            return err
        return check_exprs(e.values, gamma)
    if isinstance(e, (ast.List, ast.Tuple)):
        return check_exprs(e.elts, gamma)
    if isinstance(e, ast.ListComp):
        return check_comprehension(e.elt, e.generators, gamma)
    raise AssertionError(f'unexpected expression: {type(e).__name__}')

def check_comprehension(elt: ast.expr, generators: list[ast.comprehension], gamma: Context) -> Result:
    if not generators:
        return check_expr(elt, gamma)
    g = generators[0]
    err = check_expr(g.iter, gamma)
    if not is_ok(err):
        return err
    gamma_ = extend(gamma, {n: TT for n in names_in_target(g.target)})
    err = check_exprs(g.ifs, gamma_)
    if not is_ok(err):
        return err
    return check_comprehension(elt, generators[1:], gamma_)

def check_exprs(es: list[ast.expr], gamma: Context) -> Result:
    if not es:
        return ok()
    err = check_expr(es[0], gamma)
    if not is_ok(err):
        return err
    return check_exprs(es[1:], gamma)

def _is_catch_all(p: ast.pattern) -> bool:
    return isinstance(p, ast.MatchAs) and p.pattern is None

def _literal_value(pat: ast.MatchValue) -> object:
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
        return _literal_value(p) == _literal_value(q)
    if isinstance(p, ast.MatchSingleton) and isinstance(q, ast.MatchSingleton):
        return p.value is q.value
    if isinstance(p, ast.MatchSequence) and isinstance(q, ast.MatchSequence):
        if len(p.patterns) != len(q.patterns):
            return False
        return all((subsumes(pi, qi) for pi, qi in zip(p.patterns, q.patterns)))
    return False

def _pattern_vars(p: ast.pattern) -> list[str]:
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return []
    if isinstance(p, ast.MatchAs):
        sub = _pattern_vars(p.pattern) if p.pattern is not None else []
        return sub + ([p.name] if p.name else [])
    if isinstance(p, ast.MatchSequence):
        return [v for sub in p.patterns for v in _pattern_vars(sub)]
    raise AssertionError(f'unexpected pattern: {type(p).__name__}')

def check_pattern_list(patterns: list[ast.pattern], node: ast.AST) -> Result:
    for i, p in enumerate(patterns):
        vars_ = _pattern_vars(p)
        if len(vars_) != len(set(vars_)):
            return ill_formed(node, f'repeated variable in pattern {i + 1}')
        for j in range(i):
            if subsumes(p, patterns[j]):
                return ill_formed(node, f'case {i + 1} unreachable: subsumed by case {j + 1}')
    return ok()

def binds(pattern: ast.pattern) -> set[str]:
    if isinstance(pattern, (ast.MatchValue, ast.MatchSingleton)):
        return set()
    if isinstance(pattern, ast.MatchAs):
        sub = binds(pattern.pattern) if pattern.pattern is not None else set()
        return sub | ({pattern.name} if pattern.name else set())
    if isinstance(pattern, ast.MatchSequence):
        return set().union(*(binds(p) for p in pattern.patterns))
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
    if not es:
        return set()
    return fv(es[0]) | fv_list(es[1:])

def fv_comprehension(elt: ast.expr, generators: list[ast.comprehension]) -> set[str]:
    if not generators:
        return fv(elt)
    g = generators[0]
    target_names = names_in_target(g.target)
    rest = fv_list(g.ifs) | fv_comprehension(elt, generators[1:])
    return fv(g.iter) | rest - target_names

def names_in_target(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple):
        return _names_in_targets(target.elts)
    return set()

def _names_in_targets(targets: list[ast.expr]) -> set[str]:
    if not targets:
        return set()
    return names_in_target(targets[0]) | _names_in_targets(targets[1:])

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
    if not es:
        return set()
    return captures(es[0]) | captures_list(es[1:])

def captures_comprehension(elt: ast.expr, generators: list[ast.comprehension]) -> set[str]:
    if not generators:
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
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def fv_block(block: list[ast.stmt]) -> set[str]:
    if not block:
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
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def assigns_block(block: list[ast.stmt]) -> set[str]:
    if not block:
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
    raise AssertionError(f'unexpected statement: {type(s).__name__}')

def captures_block(block: list[ast.stmt]) -> set[str]:
    if not block:
        return set()
    return captures_stmt(block[0]) | captures_block(block[1:])

def captures_region(defs: list[ast.FunctionDef]) -> set[str]:
    f_names = {d.name for d in defs}
    return _captures_region_bodies(defs) - f_names

def _captures_region_bodies(defs: list[ast.FunctionDef]) -> set[str]:
    if not defs:
        return set()
    d = defs[0]
    params = {a.arg for a in d.args.args}
    own = fv_block(d.body) - params - assigns_block(d.body)
    return own | _captures_region_bodies(defs[1:])

def captures_item(item: Item) -> set[str]:
    if isinstance(item, list):
        return captures_region(item)
    return captures_stmt(item)

def assigns_item(item: Item) -> set[str]:
    if isinstance(item, list):
        return {d.name for d in item}
    return assigns_stmt(item)

def assigns_items(items: list[Item]) -> set[str]:
    if not items:
        return set()
    return assigns_item(items[0]) | assigns_items(items[1:])

def find_first_reassigning(items: list[Item], names: set[str]) -> Optional[ast.AST]:
    if not items:
        return None
    if assigns_item(items[0]) & names:
        return items[0][0] if isinstance(items[0], list) else items[0]
    return find_first_reassigning(items[1:], names)

def _find_nested_import(stmts: list[ast.stmt], nested: bool = False) -> ast.AST | None:
    """Return the first import statement appearing in a non-top-level context.
    nested=True means stmts themselves are inside a non-top-level body."""
    for s in stmts:
        if nested and isinstance(s, (ast.Import, ast.ImportFrom)):
            return s
        if isinstance(s, ast.FunctionDef):
            r = _find_nested_import(s.body, nested=True)
            if r is not None:
                return r
        if isinstance(s, ast.If):
            r = _find_nested_import(s.body, nested=True) or _find_nested_import(s.orelse, nested=True)
            if r is not None:
                return r
        if isinstance(s, ast.Match):
            for case in s.cases:
                r = _find_nested_import(case.body, nested=True)
                if r is not None:
                    return r
    return None

def check_module(tree: ast.AST) -> Result:
    assert isinstance(tree, ast.Module)
    if not tree.body:
        return ok()
    nested = _find_nested_import(tree.body)
    if nested is not None:
        return ill_formed(nested, '[import] import only allowed at module top level')
    return check_block(tree.body, dict(BUILTINS))

def check_file(filename: str) -> Result:
    source = open(filename).read()
    tree = ast.parse(source, filename=filename)
    return check_module(tree)

def format_result(result: Result, filename: str) -> str:
    if is_ok(result):
        return f'{filename}: ok'
    assert result is not None
    line = result.line
    col = result.col
    msg = result.msg
    if line is not None:
        return f'{filename}:{line}:{col}: {msg}'
    return f'{filename}: {msg}'

def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: purepy_check.py <file.py> [<file.py> ...]')
        sys.exit(1)
    exit_code = 0
    for filename in sys.argv[1:]:
        result = check_file(filename)
        print(format_result(result, filename))
        if not is_ok(result):
            assert result is not None
            exit_code = result.kind
    sys.exit(exit_code)
if __name__ == '__main__':
    main()
