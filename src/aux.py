import ast
from itertools import dropwhile, takewhile

from type_syntax import QualifiedName, TypeExpr, Var, dotted_name, parse_annotation

# A PurePy statement: a Python statement, or a mutual region of consecutive defs. A Python body
# (a statement list) represents the spec's right-nested sequence s s'.
type Statement = ast.stmt | list[ast.FunctionDef]


def is_import(s: ast.stmt) -> bool:
    return isinstance(s, (ast.Import, ast.ImportFrom))


def split_imports(body: list[ast.stmt]) -> tuple[list[ast.stmt], list[ast.stmt]]:
    return list(takewhile(is_import, body)), list(dropwhile(is_import, body))


def statements(body: list[ast.stmt]) -> list[Statement]:
    if len(body) == 0:
        return []
    head = body[0]
    rest = body[1:]
    if isinstance(head, ast.FunctionDef):
        return extend_region([head], rest)
    return [head] + statements(rest)


def extend_region(region: list[ast.FunctionDef], rest: list[ast.stmt]) -> list[Statement]:
    if len(rest) == 0:
        return [region]
    head = rest[0]
    if isinstance(head, ast.FunctionDef):
        return extend_region(region + [head], rest[1:])
    return [region] + statements(rest)


def binds(pattern: ast.pattern) -> set[Var]:
    match pattern:
        case ast.MatchValue():
            return set()
        case ast.MatchSingleton():
            return set()
        case ast.MatchAs(pattern=p, name=x):
            sub = binds(p) if p is not None else set()
            return sub | ({x} if x else set())
        case ast.MatchSequence(patterns=ps):
            return set().union(*(binds(p) for p in ps))
        case ast.MatchMapping(patterns=ps):
            return set().union(*(binds(p) for p in ps))
        case ast.MatchClass(patterns=ps, kwd_patterns=ps_):
            return set().union(*(binds(p) for p in list(ps) + list(ps_)))
        case _:
            raise AssertionError(f"unexpected pattern: {type(pattern).__name__}")


def fv_e(e: ast.expr) -> set[Var]:
    match e:
        case ast.Name(id=x):
            return {x}
        case ast.Constant():
            return set()
        case ast.Lambda():
            params = {a.arg for a in e.args.args}
            return fv_e(e.body) - params
        case ast.Call():
            return fv_e(e.func) | fv_e_list(e.args) | fv_e_list([k.value for k in e.keywords])
        case ast.BinOp():
            return fv_e(e.left) | fv_e(e.right)
        case ast.UnaryOp(operand=e_):
            return fv_e(e_)
        case ast.BoolOp(values=es):
            return fv_e_list(es)
        case ast.Compare(left=e_, comparators=es):
            return fv_e(e_) | fv_e_list(es)
        case ast.IfExp():
            return fv_e(e.test) | fv_e(e.body) | fv_e(e.orelse)
        case ast.Attribute(value=e_):
            return fv_e(e_)
        case ast.Subscript():
            return fv_e(e.value) | fv_e(e.slice)
        case ast.List(elts=es):
            return fv_e_list(es)
        case ast.Tuple(elts=es):
            return fv_e_list(es)
        case ast.Dict():
            return fv_e_list(dict_keys(e)) | fv_e_list(e.values)
        case ast.ListComp():
            return fv_e_comprehension([e.elt], e.generators)
        case ast.DictComp():
            return fv_e_comprehension([e.key, e.value], e.generators)
        case _:
            raise AssertionError(f"unexpected expression: {type(e).__name__}")


def fv_e_list(es: list[ast.expr]) -> set[Var]:
    if len(es) == 0:
        return set()
    return fv_e(es[0]) | fv_e_list(es[1:])


def fv_e_comprehension(elts: list[ast.expr], generators: list[ast.comprehension]) -> set[Var]:
    if len(generators) == 0:
        return fv_e_list(elts)
    g = generators[0]
    rest = fv_e_list(g.ifs) | fv_e_comprehension(elts, generators[1:])
    return fv_e(g.iter) | (rest - {target_name(g)})


def dict_keys(e: ast.Dict) -> list[ast.expr]:
    keys = [k for k in e.keys if k is not None]
    assert len(keys) == len(e.keys), "dict unpacking rejected by syntax check"
    return keys


def target_name(g: ast.comprehension) -> str:
    assert isinstance(g.target, ast.Name)
    return g.target.id


def captures_e(e: ast.expr) -> set[Var]:
    match e:
        case ast.Lambda():
            params = {a.arg for a in e.args.args}
            return fv_e(e.body) - params
        case ast.Name():
            return set()
        case ast.Constant():
            return set()
        case ast.Call():
            return (
                captures_e(e.func)
                | captures_e_list(e.args)
                | captures_e_list([k.value for k in e.keywords])
            )
        case ast.BinOp():
            return captures_e(e.left) | captures_e(e.right)
        case ast.UnaryOp(operand=e_):
            return captures_e(e_)
        case ast.BoolOp(values=es):
            return captures_e_list(es)
        case ast.Compare(left=e_, comparators=es):
            return captures_e(e_) | captures_e_list(es)
        case ast.IfExp():
            return captures_e(e.test) | captures_e(e.body) | captures_e(e.orelse)
        case ast.Attribute(value=e_):
            return captures_e(e_)
        case ast.Subscript():
            return captures_e(e.value) | captures_e(e.slice)
        case ast.List(elts=es):
            return captures_e_list(es)
        case ast.Tuple(elts=es):
            return captures_e_list(es)
        case ast.Dict():
            return captures_e_list(dict_keys(e)) | captures_e_list(e.values)
        case ast.ListComp():
            return captures_quals(e.generators) | (captures_e(e.elt) - binds_quals(e.generators))
        case ast.DictComp():
            return captures_quals(e.generators) | (
                (captures_e(e.key) | captures_e(e.value)) - binds_quals(e.generators)
            )
        case _:
            raise AssertionError(f"unexpected expression: {type(e).__name__}")


def captures_e_list(es: list[ast.expr]) -> set[Var]:
    if len(es) == 0:
        return set()
    return captures_e(es[0]) | captures_e_list(es[1:])


def captures_quals(generators: list[ast.comprehension]) -> set[Var]:
    if len(generators) == 0:
        return set()
    g = generators[0]
    rest = captures_e_list(g.ifs) | captures_quals(generators[1:])
    return captures_e(g.iter) | (rest - {target_name(g)})


def binds_quals(generators: list[ast.comprehension]) -> set[Var]:
    return {target_name(g) for g in generators}


def assigns_stmt(s: ast.stmt) -> set[Var]:
    match s:
        case ast.Pass():
            return set()
        case ast.Expr():
            return set()
        case ast.Return():
            return set()
        case ast.Assert():
            return set()
        case ast.Assign():
            (target,) = s.targets
            assert isinstance(target, ast.Name)
            return {target.id}
        case ast.AnnAssign():
            assert isinstance(s.target, ast.Name)
            return {s.target.id}
        case ast.If(body=ss, orelse=ss_):
            return assigns_body(ss) | assigns_body(ss_)
        case ast.Match():
            return set().union(*(binds(case.pattern) | assigns_body(case.body) for case in s.cases))
        case ast.FunctionDef(name=x):
            return {x}
        case ast.ClassDef(name=x):
            return {x}
        case _:
            raise AssertionError(f"unexpected statement: {type(s).__name__}")


def assigns_body(body: list[ast.stmt]) -> set[Var]:
    if len(body) == 0:
        return set()
    return assigns_stmt(body[0]) | assigns_body(body[1:])


def declares(s: ast.stmt) -> list[tuple[Var, ast.stmt]]:
    """Names declared in `s` with their declaring nodes, in textual order and with repeats."""
    match s:
        case ast.AnnAssign():
            assert isinstance(s.target, ast.Name)
            return [(s.target.id, s)]
        case ast.If(body=ss, orelse=ss_):
            return declares_body(ss) + declares_body(ss_)
        case ast.Match():
            return [d for case in s.cases for d in declares_body(case.body)]
        case ast.FunctionDef(name=x):
            return [(x, s)]
        case ast.ClassDef(name=x):
            return [(x, s)]
        case _:
            return []


def declares_body(body: list[ast.stmt]) -> list[tuple[Var, ast.stmt]]:
    return [d for s in body for d in declares(s)]


def assign_targets(body: list[ast.stmt]) -> list[tuple[Var, ast.stmt]]:
    """Targets of the unannotated assignments in `body`, in textual order, not descending into defs."""
    out: list[tuple[Var, ast.stmt]] = []
    for s in body:
        match s:
            case ast.Assign(targets=[ast.Name(id=x)]):
                out.append((x, s))
            case ast.If(body=ss, orelse=ss_):
                out += assign_targets(ss) + assign_targets(ss_)
            case ast.Match():
                out += [t for case in s.cases for t in assign_targets(case.body)]
            case _:
                pass
    return out


def pattern_bound(body: list[ast.stmt]) -> set[Var]:
    """Variables bound by the patterns of the match statements in `body`, not descending into defs."""
    out: set[Var] = set()
    for s in body:
        match s:
            case ast.If(body=ss, orelse=ss_):
                out |= pattern_bound(ss) | pattern_bound(ss_)
            case ast.Match():
                out |= set().union(
                    *(binds(case.pattern) | pattern_bound(case.body) for case in s.cases)
                )
            case _:
                pass
    return out


def redeclaration(body: list[ast.stmt]) -> tuple[Var, ast.stmt] | None:
    """Second declaration of a name declared twice in `body`, if any."""
    ds = declares_body(body)
    return next(((x, node) for i, (x, node) in enumerate(ds) if x in [y for y, _ in ds[:i]]), None)


def own_fields(node: ast.ClassDef) -> tuple[tuple[Var, TypeExpr], ...]:
    return tuple(
        (t.target.id, type_expr(t.annotation))
        for t in node.body
        if isinstance(t, ast.AnnAssign) and isinstance(t.target, ast.Name)
    )


def type_expr(annotation: ast.expr | None) -> TypeExpr:
    assert annotation is not None, "missing annotation rejected by syntax check"
    t = parse_annotation(annotation)
    assert t is not None, "unsupported annotation rejected by syntax check"
    return t


def qualified_name(e: ast.expr) -> QualifiedName:
    q = dotted_name(e)
    assert q is not None
    return q
