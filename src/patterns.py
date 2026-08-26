import ast

import reasons
from aux import binds_seq, qualified_name
from contexts import (
    ModuleContext,
    ancestors,
    class_entry,
    field_map,
    fields,
    short_name,
)
from reasons import IllFormedModule
from syntax import PatList, PatTuple


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
    raise AssertionError(f"unexpected MatchValue payload: {type(v).__name__}")


def dict_key(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)
    return k.value


def subsumes(p: ast.pattern, q: ast.pattern, ctx: ModuleContext) -> bool:
    if isinstance(q, ast.MatchAs) and q.pattern is not None:
        return subsumes(p, q.pattern, ctx)
    if isinstance(p, ast.MatchAs) and p.pattern is not None:
        return subsumes(p.pattern, q, ctx)
    if isinstance(q, ast.MatchAs) and q.pattern is None:
        return True
    if isinstance(p, ast.MatchValue) and isinstance(q, ast.MatchValue):
        return literal_value(p) == literal_value(q)
    if isinstance(p, ast.MatchSingleton) and isinstance(q, ast.MatchSingleton):
        return p.value is q.value
    if isinstance(p, ast.MatchMapping) and isinstance(q, ast.MatchMapping):
        p_keys = {dict_key(k): sub for k, sub in zip(p.keys, p.patterns)}
        q_keys = {dict_key(k): sub for k, sub in zip(q.keys, q.patterns)}
        if not set(q_keys) <= set(p_keys):
            return False
        return all(subsumes(p_keys[k], sub, ctx) for k, sub in q_keys.items())
    if isinstance(p, ast.MatchSequence) and isinstance(q, ast.MatchSequence):
        assert isinstance(p, (PatList, PatTuple)) and isinstance(q, (PatList, PatTuple))
        if type(p) is not type(q):
            return False
        if len(p.patterns) != len(q.patterns):
            return False
        return all(subsumes(pi, qi, ctx) for pi, qi in zip(p.patterns, q.patterns))
    if isinstance(p, ast.MatchClass) and isinstance(q, ast.MatchClass):
        c_p, c_q = class_entry(p.cls, ctx), class_entry(q.cls, ctx)
        if c_p is None or c_q is None:
            return False
        if not any(a.name == c_q.name for a in ancestors(c_p)):
            return False
        map_p = field_map(c_p, p.patterns, p.kwd_attrs, p.kwd_patterns)
        map_q = field_map(c_q, q.patterns, q.kwd_attrs, q.kwd_patterns)
        if map_p is None or map_q is None:
            return False
        return all(subsumes(map_p[x], map_q[x], ctx) for x in fields(c_q))
    return False


def check_pattern(p: ast.pattern, ctx: ModuleContext) -> None:
    if isinstance(p, ast.MatchClass):
        entry = class_entry(p.cls, ctx)
        if entry is None:
            raise IllFormedModule(
                p,
                reasons.UnknownClassInPattern(
                    qualified_name(p.cls)
                    if isinstance(p.cls, (ast.Name, ast.Attribute))
                    else ast.unparse(p.cls)
                ),
            )
        c_name, xs = short_name(entry), fields(entry)
        if field_map(entry, p.patterns, p.kwd_attrs, p.kwd_patterns) is None:
            n = len(p.patterns)
            if n + len(p.kwd_attrs) != len(xs):
                raise IllFormedModule(
                    p,
                    reasons.PatternArityMismatch(c_name, len(xs), n + len(p.kwd_attrs)),
                )
            if len(p.kwd_attrs) != len(set(p.kwd_attrs)):
                raise IllFormedModule(p, reasons.DuplicatePatternKeyword(c_name))
            raise IllFormedModule(
                p, reasons.UnknownFieldInPattern(c_name, tuple(sorted(set(xs[n:]))))
            )
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


def check_pattern_list(
    patterns: list[ast.pattern], node: ast.AST, ctx: ModuleContext
) -> None:
    for i, p in enumerate(patterns):
        check_pattern(p, ctx)
        vars_ = binds_seq(p)
        if len(vars_) != len(set(vars_)):
            raise IllFormedModule(node, reasons.NonlinearPattern(i + 1))
        for j in range(i):
            if subsumes(p, patterns[j], ctx):
                raise IllFormedModule(node, reasons.UnreachableCase(i + 1, j + 1))
