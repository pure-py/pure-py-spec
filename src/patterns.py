import ast

from contexts import (
    ModuleContext,
    class_entry,
    short_name,
)
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
