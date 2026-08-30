import ast

import reasons
from aux import binds_seq, qualified_name
from contexts import (
    ModuleContext,
    class_entry,
    field_map,
    fields,
    short_name,
)
from reasons import IllFormedModule
from syntax import PatList, PatTuple
from type_syntax import (
    LiteralType,
    render,
)


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


def literal_of(p: ast.pattern) -> object:
    if isinstance(p, ast.MatchSingleton):
        return p.value
    assert isinstance(p, ast.MatchValue)
    return literal_value(p)


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


