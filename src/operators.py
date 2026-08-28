import ast
from collections.abc import Callable, Sequence

from contexts import ModuleContext
from subtyping import comparable, join, subtype
from type_syntax import (
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    base_type,
)

type BinarySignature = Callable[[Type, Type, ModuleContext], Type | None]
type UnarySignature = Callable[[Type, ModuleContext], Type | None]


def both(
    s: Type, t: Type, param: Type, result: Type, ctx: ModuleContext
) -> Type | None:
    return result if subtype(s, param, ctx) and subtype(t, param, ctx) else None


def equality(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return Primitive.BOOL if comparable(s, t, ctx) else None


def membership_list(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if isinstance(t, ListType) and comparable(s, t.elem, ctx):
        return Primitive.BOOL
    return None


def membership_tuple(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if isinstance(t, TupleType) and comparable(s, join(t.components, ctx), ctx):
        return Primitive.BOOL
    return None


def membership_str(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return both(s, t, Primitive.STR, Primitive.BOOL, ctx)


def membership_dict(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if isinstance(t, DictType) and subtype(s, Primitive.STR, ctx):
        return Primitive.BOOL
    return None


def ordering_number(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return both(s, t, Primitive.FLOAT, Primitive.BOOL, ctx)


def ordering_str(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return both(s, t, Primitive.STR, Primitive.BOOL, ctx)


def arithmetic_int(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return both(s, t, Primitive.INT, Primitive.INT, ctx)


def arithmetic_float(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return both(s, t, Primitive.FLOAT, Primitive.FLOAT, ctx)


def concat_str(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return both(s, t, Primitive.STR, Primitive.STR, ctx)


def concat_list(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if isinstance(s, ListType) and isinstance(t, ListType):
        return ListType(join((s.elem, t.elem), ctx))
    return None


def concat_tuple(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if isinstance(s, TupleType) and isinstance(t, TupleType):
        return TupleType(s.components + t.components)
    return None


def repeat_str(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if subtype(s, Primitive.STR, ctx) and subtype(t, Primitive.INT, ctx):
        return Primitive.STR
    return None


def repeat_str_left(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return repeat_str(t, s, ctx)


def repeat_list(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if isinstance(s, ListType) and subtype(t, Primitive.INT, ctx):
        return s
    return None


def repeat_list_left(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    return repeat_list(t, s, ctx)


def power_int(s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    if subtype(s, Primitive.INT, ctx) and isinstance(t, LiteralType):
        exponent = t.value
        if isinstance(exponent, int) and not isinstance(exponent, bool):
            return Primitive.FLOAT if exponent < 0 else Primitive.INT
    return None


BINARY_SIGNATURES: dict[str, tuple[BinarySignature, ...]] = {
    "==": (equality,),
    "!=": (equality,),
    "in": (membership_list, membership_tuple, membership_str, membership_dict),
    "not in": (membership_list, membership_tuple, membership_str, membership_dict),
    "<": (ordering_number, ordering_str),
    "<=": (ordering_number, ordering_str),
    ">": (ordering_number, ordering_str),
    ">=": (ordering_number, ordering_str),
    "+": (arithmetic_int, arithmetic_float, concat_str, concat_list, concat_tuple),
    "-": (arithmetic_int, arithmetic_float),
    "*": (
        arithmetic_int,
        arithmetic_float,
        repeat_str,
        repeat_str_left,
        repeat_list,
        repeat_list_left,
    ),
    "//": (arithmetic_int, arithmetic_float),
    "%": (arithmetic_int, arithmetic_float),
    "/": (arithmetic_float,),
    "**": (power_int, arithmetic_float),
}


def negate_bool(s: Type, ctx: ModuleContext) -> Type | None:
    return Primitive.BOOL if subtype(s, Primitive.BOOL, ctx) else None


def sign_int(s: Type, ctx: ModuleContext) -> Type | None:
    return Primitive.INT if subtype(s, Primitive.INT, ctx) else None


def sign_float(s: Type, ctx: ModuleContext) -> Type | None:
    return Primitive.FLOAT if subtype(s, Primitive.FLOAT, ctx) else None


UNARY_SIGNATURES: dict[str, tuple[UnarySignature, ...]] = {
    "not": (negate_bool,),
    "+": (sign_int, sign_float),
    "-": (sign_int, sign_float),
}

BINARY_NAMES: dict[type[ast.AST], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.In: "in",
    ast.NotIn: "not in",
}

UNARY_NAMES: dict[type[ast.AST], str] = {
    ast.Not: "not",
    ast.UAdd: "+",
    ast.USub: "-",
}


def first_result(results: Sequence[Type | None]) -> Type | None:
    return next((r for r in results if r is not None), None)


def resolve_binary(op: str, s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    """The result of applying `op`, trying the operand types as synthesised and
    then at their base types, which is how a literal operand checks against a
    signature written for its base type."""
    exact = first_result([sig(s, t, ctx) for sig in BINARY_SIGNATURES[op]])
    if exact is not None:
        return exact
    return first_result(
        [sig(base_type(s), base_type(t), ctx) for sig in BINARY_SIGNATURES[op]]
    )


def resolve_unary(op: str, s: Type, ctx: ModuleContext) -> Type | None:
    exact = first_result([sig(s, ctx) for sig in UNARY_SIGNATURES[op]])
    if exact is not None:
        return exact
    return first_result([sig(base_type(s), ctx) for sig in UNARY_SIGNATURES[op]])
