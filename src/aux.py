from __future__ import annotations

import ast
from itertools import dropwhile, takewhile
from typing import Optional, Union

BlockElement = Union[ast.stmt, list[ast.FunctionDef]]

def is_import(s: ast.stmt) -> bool:
    return isinstance(s, (ast.Import, ast.ImportFrom))

def split_imports(body: list[ast.stmt]) -> tuple[list[ast.stmt], list[ast.stmt]]:
    return list(takewhile(is_import, body)), list(dropwhile(is_import, body))

def find_import(stmts: list[ast.stmt]) -> Optional[ast.stmt]:
    return next((s for s in stmts if isinstance(s, (ast.Import, ast.ImportFrom))), None)

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

def annotate_seq_kinds(tree: ast.AST, source: str) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.MatchSequence):
            segment = ast.get_source_segment(source, node)
            setattr(node, 'is_list_pattern', segment is not None and segment.lstrip().startswith('['))

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

def own_fields_of(node: ast.ClassDef) -> list[str]:
    return [t.target.id for t in node.body
            if isinstance(t, ast.AnnAssign) and isinstance(t.target, ast.Name)]
