import ast
from itertools import dropwhile, takewhile

from type_syntax import TypeExpr, dotted_name, parse_annotation

# A PurePy statement: a Python statement, or a mutual region of consecutive defs. A Python body
# (a statement list) represents the spec's right-nested sequence s s'.
type Statement = ast.stmt | list[ast.FunctionDef]


def is_import(s: ast.stmt) -> bool:
    return isinstance(s, (ast.Import, ast.ImportFrom))


def split_imports(body: list[ast.stmt]) -> tuple[list[ast.stmt], list[ast.stmt]]:
    return list(takewhile(is_import, body)), list(dropwhile(is_import, body))


def find_import(stmts: list[ast.stmt]) -> ast.stmt | None:
    return next((s for s in stmts if isinstance(s, (ast.Import, ast.ImportFrom))), None)


def statements(body: list[ast.stmt]) -> list[Statement]:
    if len(body) == 0:
        return []
    head = body[0]
    rest = body[1:]
    if isinstance(head, ast.FunctionDef):
        return extend_region([head], rest)
    return [head] + statements(rest)


def extend_region(
    region: list[ast.FunctionDef], rest: list[ast.stmt]
) -> list[Statement]:
    if len(rest) == 0:
        return [region]
    head = rest[0]
    if isinstance(head, ast.FunctionDef):
        return extend_region(region + [head], rest[1:])
    return [region] + statements(rest)


def binds_seq(pattern: ast.pattern) -> list[str]:
    if isinstance(pattern, (ast.MatchValue, ast.MatchSingleton)):
        return []
    if isinstance(pattern, ast.MatchAs):
        sub = binds_seq(pattern.pattern) if pattern.pattern is not None else []
        return sub + ([pattern.name] if pattern.name else [])
    if isinstance(pattern, ast.MatchSequence):
        return [x for p in pattern.patterns for x in binds_seq(p)]
    if isinstance(pattern, ast.MatchClass):
        return [
            x
            for p in list(pattern.patterns) + list(pattern.kwd_patterns)
            for x in binds_seq(p)
        ]
    if isinstance(pattern, ast.MatchMapping):
        return [x for p in pattern.patterns for x in binds_seq(p)]
    raise AssertionError(f"unexpected pattern: {type(pattern).__name__}")


def binds(pattern: ast.pattern) -> set[str]:
    return set(binds_seq(pattern))


def fv_e(e: ast.expr) -> set[str]:
    if isinstance(e, ast.Name):
        return {e.id}
    if isinstance(e, ast.Constant):
        return set()
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        return fv_e(e.body) - params
    if isinstance(e, ast.Call):
        return fv_e(e.func) | fv_e_list(e.args)
    if isinstance(e, ast.BinOp):
        return fv_e(e.left) | fv_e(e.right)
    if isinstance(e, ast.UnaryOp):
        return fv_e(e.operand)
    if isinstance(e, ast.BoolOp):
        return fv_e_list(e.values)
    if isinstance(e, ast.Compare):
        return fv_e(e.left) | fv_e_list(e.comparators)
    if isinstance(e, ast.IfExp):
        return fv_e(e.test) | fv_e(e.body) | fv_e(e.orelse)
    if isinstance(e, ast.Attribute):
        return fv_e(e.value)
    if isinstance(e, ast.Subscript):
        return fv_e(e.value) | fv_e(e.slice)
    if isinstance(e, (ast.List, ast.Tuple)):
        return fv_e_list(e.elts)
    if isinstance(e, ast.Dict):
        return fv_e_list([k for k in e.keys if k is not None]) | fv_e_list(e.values)
    if isinstance(e, ast.ListComp):
        return fv_e_comprehension([e.elt], e.generators)
    if isinstance(e, ast.DictComp):
        return fv_e_comprehension([e.key, e.value], e.generators)
    raise AssertionError(f"unexpected expression: {type(e).__name__}")


def fv_e_list(es: list[ast.expr]) -> set[str]:
    if len(es) == 0:
        return set()
    return fv_e(es[0]) | fv_e_list(es[1:])


def fv_e_comprehension(
    elts: list[ast.expr], generators: list[ast.comprehension]
) -> set[str]:
    if len(generators) == 0:
        return fv_e_list(elts)
    g = generators[0]
    target_names = names_in_target(g.target)
    rest = fv_e_list(g.ifs) | fv_e_comprehension(elts, generators[1:])
    return fv_e(g.iter) | rest - target_names


def names_in_target(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Tuple):
        return {n for t in target.elts for n in names_in_target(t)}
    return set()


def captures_e(e: ast.expr) -> set[str]:
    if isinstance(e, ast.Lambda):
        params = {a.arg for a in e.args.args}
        return fv_e(e.body) - params
    if isinstance(e, ast.Name):
        return set()
    if isinstance(e, ast.Constant):
        return set()
    if isinstance(e, ast.Call):
        return captures_e(e.func) | captures_e_list(e.args)
    if isinstance(e, ast.BinOp):
        return captures_e(e.left) | captures_e(e.right)
    if isinstance(e, ast.UnaryOp):
        return captures_e(e.operand)
    if isinstance(e, ast.BoolOp):
        return captures_e_list(e.values)
    if isinstance(e, ast.Compare):
        return captures_e(e.left) | captures_e_list(e.comparators)
    if isinstance(e, ast.IfExp):
        return captures_e(e.test) | captures_e(e.body) | captures_e(e.orelse)
    if isinstance(e, ast.Attribute):
        return captures_e(e.value)
    if isinstance(e, ast.Subscript):
        return captures_e(e.value) | captures_e(e.slice)
    if isinstance(e, (ast.List, ast.Tuple)):
        return captures_e_list(e.elts)
    if isinstance(e, ast.Dict):
        return captures_e_list([k for k in e.keys if k is not None]) | captures_e_list(
            e.values
        )
    if isinstance(e, ast.ListComp):
        return captures_quals(e.generators) | (
            captures_e(e.elt) - binds_quals(e.generators)
        )
    if isinstance(e, ast.DictComp):
        return captures_quals(e.generators) | (
            (captures_e(e.key) | captures_e(e.value)) - binds_quals(e.generators)
        )
    raise AssertionError(f"unexpected expression: {type(e).__name__}")


def captures_e_list(es: list[ast.expr]) -> set[str]:
    if len(es) == 0:
        return set()
    return captures_e(es[0]) | captures_e_list(es[1:])


def captures_quals(generators: list[ast.comprehension]) -> set[str]:
    if len(generators) == 0:
        return set()
    g = generators[0]
    rest = captures_e_list(g.ifs) | captures_quals(generators[1:])
    return captures_e(g.iter) | rest - names_in_target(g.target)


def binds_quals(generators: list[ast.comprehension]) -> set[str]:
    return {n for g in generators for n in names_in_target(g.target)}


def fv_stmt(s: ast.stmt) -> set[str]:
    if isinstance(s, ast.Pass):
        return set()
    if isinstance(s, ast.Assign):
        return fv_e(s.value)
    if isinstance(s, ast.AnnAssign):
        return fv_e(s.value) if s.value is not None else set()
    if isinstance(s, ast.Expr):
        return fv_e(s.value)
    if isinstance(s, ast.Return):
        return fv_e(s.value) if s.value is not None else set()
    if isinstance(s, ast.Assert):
        result = fv_e(s.test)
        if s.msg is not None:
            result = result | fv_e(s.msg)
        return result
    if isinstance(s, ast.If):
        return fv_e(s.test) | fv_body(s.body) | fv_body(s.orelse)
    if isinstance(s, ast.Match):
        return fv_e(s.subject) | set().union(
            *(fv_body(case.body) - binds(case.pattern) for case in s.cases)
        )
    if isinstance(s, ast.FunctionDef):
        params = {a.arg for a in s.args.args}
        return fv_body(s.body) - params - {s.name}
    if isinstance(s, ast.ClassDef):
        return set()
    raise AssertionError(f"unexpected statement: {type(s).__name__}")


def fv_body(body: list[ast.stmt]) -> set[str]:
    if len(body) == 0:
        return set()
    return fv_stmt(body[0]) | fv_body(body[1:])


def assigns_stmt(s: ast.stmt) -> set[str]:
    if isinstance(s, (ast.Pass, ast.Expr, ast.Return, ast.Assert)):
        return set()
    if isinstance(s, ast.Assign):
        return {t.id for t in s.targets if isinstance(t, ast.Name)}
    if isinstance(s, ast.AnnAssign):
        return {s.target.id} if isinstance(s.target, ast.Name) else set()
    if isinstance(s, ast.If):
        return assigns_body(s.body) | assigns_body(s.orelse)
    if isinstance(s, ast.Match):
        return set().union(
            *(binds(case.pattern) | assigns_body(case.body) for case in s.cases)
        )
    if isinstance(s, ast.FunctionDef):
        return {s.name}
    if isinstance(s, ast.ClassDef):
        return {s.name}
    raise AssertionError(f"unexpected statement: {type(s).__name__}")


def assigns_body(body: list[ast.stmt]) -> set[str]:
    if len(body) == 0:
        return set()
    return assigns_stmt(body[0]) | assigns_body(body[1:])


def captures(s: ast.stmt) -> set[str]:
    if isinstance(s, ast.Pass):
        return set()
    if isinstance(s, ast.Assign):
        return captures_e(s.value)
    if isinstance(s, ast.AnnAssign):
        return captures_e(s.value) if s.value is not None else set()
    if isinstance(s, ast.Expr):
        return captures_e(s.value)
    if isinstance(s, ast.Return):
        return captures_e(s.value) if s.value is not None else set()
    if isinstance(s, ast.Assert):
        result = captures_e(s.test)
        if s.msg is not None:
            result = result | captures_e(s.msg)
        return result
    if isinstance(s, ast.If):
        return captures_e(s.test) | captures_body(s.body) | captures_body(s.orelse)
    if isinstance(s, ast.Match):
        return captures_e(s.subject) | set().union(
            *(captures_body(case.body) - binds(case.pattern) for case in s.cases)
        )
    if isinstance(s, ast.FunctionDef):
        return captures_region([s])
    if isinstance(s, ast.ClassDef):
        return set()
    raise AssertionError(f"unexpected statement: {type(s).__name__}")


def captures_body(body: list[ast.stmt]) -> set[str]:
    if len(body) == 0:
        return set()
    return captures(body[0]) | captures_body(body[1:])


def captures_region(defs: list[ast.FunctionDef]) -> set[str]:
    f_names = {d.name for d in defs}
    return captures_region_bodies(defs) - f_names


def captures_region_bodies(defs: list[ast.FunctionDef]) -> set[str]:
    if len(defs) == 0:
        return set()
    d = defs[0]
    params = {a.arg for a in d.args.args}
    own = fv_body(d.body) - params - assigns_body(d.body)
    return own | captures_region_bodies(defs[1:])


def captures_statement(item: Statement) -> set[str]:
    if isinstance(item, list):
        return captures_region(item)
    return captures(item)


def assigns_statement(item: Statement) -> set[str]:
    if isinstance(item, list):
        return {d.name for d in item}
    return assigns_stmt(item)


def assigns_seq(items: list[Statement]) -> set[str]:
    if len(items) == 0:
        return set()
    return assigns_statement(items[0]) | assigns_seq(items[1:])


def find_first_reassigning(items: list[Statement], names: set[str]) -> ast.AST | None:
    if len(items) == 0:
        return None
    if assigns_statement(items[0]) & names:
        return items[0][0] if isinstance(items[0], list) else items[0]
    return find_first_reassigning(items[1:], names)


def find_nested_import(stmts: list[ast.stmt], nested: bool = False) -> ast.AST | None:
    for s in stmts:
        if nested and isinstance(s, (ast.Import, ast.ImportFrom)):
            return s
        if isinstance(s, ast.FunctionDef):
            r = find_nested_import(s.body, nested=True)
            if r is not None:
                return r
        if isinstance(s, ast.If):
            r = find_nested_import(s.body, nested=True) or find_nested_import(
                s.orelse, nested=True
            )
            if r is not None:
                return r
        if isinstance(s, ast.Match):
            results = (find_nested_import(case.body, nested=True) for case in s.cases)
            r = next((x for x in results if x is not None), None)
            if r is not None:
                return r
    return None


def first_return(body: list[ast.stmt]) -> ast.Return | None:
    """The first return in a statement list, not descending into definitions."""
    for s in body:
        if isinstance(s, ast.Return):
            return s
        if isinstance(s, ast.FunctionDef):
            continue
        nested = first_return(nested_statements(s))
        if nested is not None:
            return nested
    return None


def nested_statements(s: ast.stmt) -> list[ast.stmt]:
    if isinstance(s, ast.Match):
        return [t for case in s.cases for t in case.body]
    return [c for c in ast.iter_child_nodes(s) if isinstance(c, ast.stmt)]


def own_fields(node: ast.ClassDef) -> tuple[tuple[str, TypeExpr], ...]:
    """Fields a class declares, with their type expressions."""
    declared = [
        (t.target.id, parse_annotation(t.annotation))
        for t in node.body
        if isinstance(t, ast.AnnAssign) and isinstance(t.target, ast.Name)
    ]
    assert all(t is not None for _, t in declared)
    return tuple((x, t) for x, t in declared if t is not None)


def qualified_name(e: ast.expr) -> str:
    q = dotted_name(e)
    assert q is not None
    return q
