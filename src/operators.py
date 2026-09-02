import ast
from collections.abc import Callable, Sequence

from classes import Class, field_type, fields
from contexts import ModuleContext
from subtyping import comparable, join, subtype
from type_syntax import (
    CallableType,
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
    base_type,
)

type InstantiatedRow = tuple[tuple[Type, ...], Type]
type BinaryOverload = Callable[[Type, Type, ModuleContext], InstantiatedRow | None]
type UnaryOverload = Callable[[Type, ModuleContext], InstantiatedRow | None]


def both(
    s: Type, t: Type, bound: Type, result: Type, ctx: ModuleContext
) -> InstantiatedRow | None:
    """An overload bounding both positions by `bound`."""
    return ((bound, bound), result) if subtype(s, bound) and subtype(t, bound) else None


def equality(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if not comparable(s, t):
        return None
    if not equality_type(s, ctx) or not equality_type(t, ctx):
        return None
    return (s, t), Primitive.BOOL


def equality_type(t: Type, ctx: ModuleContext) -> bool:
    """Whether values of `t` can be compared for equality: every type but a
    callable, and a container or class of equality types. A class cannot refer
    to itself through a field, since an annotation is evaluated where it
    appears."""
    if isinstance(t, CallableType):
        return False
    if isinstance(t, ListType):
        return equality_type(t.elem, ctx)
    if isinstance(t, DictType):
        return equality_type(t.value, ctx)
    if isinstance(t, TupleType):
        return all(equality_type(c, ctx) for c in t.components)
    if isinstance(t, UnionType):
        return equality_type(t.left, ctx) and equality_type(t.right, ctx)
    if isinstance(t, ClassType):
        return class_equality_type(t.c, ctx)
    return True


def class_equality_type(c: Class, ctx: ModuleContext) -> bool:
    return all(equality_type(declared(c, x), ctx) for x in fields(c))


def declared(c: Class, x: str) -> Type:
    t = field_type(c, x)
    assert t is not None
    return t


def membership_list(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if isinstance(t, ListType) and comparable(s, t.elem):
        return (s, t), Primitive.BOOL
    return None


def membership_tuple(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if isinstance(t, TupleType) and comparable(s, join(t.components)):
        return (s, t), Primitive.BOOL
    return None


def membership_str(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return both(s, t, Primitive.STR, Primitive.BOOL, ctx)


def membership_dict(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if isinstance(t, DictType) and subtype(s, Primitive.STR):
        return (Primitive.STR, t), Primitive.BOOL
    return None


def ordering_number(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return both(s, t, Primitive.FLOAT, Primitive.BOOL, ctx)


def ordering_str(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return both(s, t, Primitive.STR, Primitive.BOOL, ctx)


def arithmetic_int(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return both(s, t, Primitive.INT, Primitive.INT, ctx)


def arithmetic_float(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return both(s, t, Primitive.FLOAT, Primitive.FLOAT, ctx)


def concat_str(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return both(s, t, Primitive.STR, Primitive.STR, ctx)


def concat_list(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if isinstance(s, ListType) and isinstance(t, ListType):
        return (s, t), ListType(join((s.elem, t.elem)))
    return None


def concat_tuple(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if isinstance(s, TupleType) and isinstance(t, TupleType):
        return (s, t), TupleType(s.components + t.components)
    return None


def repeat_str(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if subtype(s, Primitive.STR) and subtype(t, Primitive.INT):
        return (Primitive.STR, Primitive.INT), Primitive.STR
    return None


def repeat_str_left(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if subtype(s, Primitive.INT) and subtype(t, Primitive.STR):
        return (Primitive.INT, Primitive.STR), Primitive.STR
    return None


def repeat_list(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if isinstance(s, ListType) and subtype(t, Primitive.INT):
        return (s, Primitive.INT), s
    return None


def repeat_list_left(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if subtype(s, Primitive.INT) and isinstance(t, ListType):
        return (Primitive.INT, t), t
    return None


def power_int(s: Type, t: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    if subtype(s, Primitive.INT) and isinstance(t, LiteralType):
        exponent = t.value
        if isinstance(exponent, int) and not isinstance(exponent, bool):
            return (Primitive.INT, t), (
                Primitive.FLOAT if exponent < 0 else Primitive.INT
            )
    return None


BINARY_OVERLOADS: dict[str, tuple[BinaryOverload, ...]] = {
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


def negate_bool(s: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return ((Primitive.BOOL,), Primitive.BOOL) if subtype(s, Primitive.BOOL) else None


def sign_int(s: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return ((Primitive.INT,), Primitive.INT) if subtype(s, Primitive.INT) else None


def sign_float(s: Type, ctx: ModuleContext) -> InstantiatedRow | None:
    return (
        ((Primitive.FLOAT,), Primitive.FLOAT) if subtype(s, Primitive.FLOAT) else None
    )


UNARY_OVERLOADS: dict[str, tuple[UnaryOverload, ...]] = {
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


def overloads_binary(
    op: str, s: Type, t: Type, ctx: ModuleContext
) -> list[InstantiatedRow]:
    """Instantiated rows of `op` at the operand types."""
    return [r for ov in BINARY_OVERLOADS[op] if (r := ov(s, t, ctx)) is not None]


def overloads_unary(op: str, s: Type, ctx: ModuleContext) -> list[InstantiatedRow]:
    return [r for ov in UNARY_OVERLOADS[op] if (r := ov(s, ctx)) is not None]


def least(rows: Sequence[InstantiatedRow]) -> InstantiatedRow | None:
    """The instantiated row whose bounds lie componentwise below every other's,
    or nothing if no row is least."""
    for cand in rows:
        if all(
            all(subtype(a, b) for a, b in zip(cand[0], other[0])) for other in rows
        ):
            return cand
    return None


def result_of_least(rows: Sequence[InstantiatedRow]) -> Type | None:
    chosen = least(rows)
    return chosen[1] if chosen is not None else None


def resolve_binary(op: str, s: Type, t: Type, ctx: ModuleContext) -> Type | None:
    """Result component of the least instantiated row at the operand types, or
    at their base types if no row applies at the operand types themselves."""
    rows = overloads_binary(op, s, t, ctx)
    if rows:
        return result_of_least(rows)
    rows = overloads_binary(op, base_type(s), base_type(t), ctx)
    return result_of_least(rows) if rows else None


def resolve_unary(op: str, s: Type, ctx: ModuleContext) -> Type | None:
    rows = overloads_unary(op, s, ctx)
    if rows:
        return result_of_least(rows)
    rows = overloads_unary(op, base_type(s), ctx)
    return result_of_least(rows) if rows else None
