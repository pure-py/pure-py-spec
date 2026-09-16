import ast
from collections.abc import Callable, Sequence

from classes import Class, ClassTable, declared_type, fields
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

type ResolvedOverload = tuple[tuple[Type, ...], Type]
type BinaryOverload = Callable[[ClassTable, Type, Type], ResolvedOverload | None]
type UnaryOverload = Callable[[ClassTable, Type], ResolvedOverload | None]


def both(
    sigma: ClassTable, s: Type, t: Type, bound: Type, result: Type
) -> ResolvedOverload | None:
    return (
        ((bound, bound), result)
        if subtype(sigma, s, bound) and subtype(sigma, t, bound)
        else None
    )


def equality(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if not comparable(sigma, s, t):
        return None
    if not equality_type(sigma, s) or not equality_type(sigma, t):
        return None
    return (s, t), Primitive.BOOL


def equality_type(sigma: ClassTable, t: Type) -> bool:
    """Whether values of `t` can be compared for equality: every type but a
    callable, and a container or class of equality types. A class cannot refer
    to itself through a field, since an annotation is evaluated where it
    appears."""
    if isinstance(t, CallableType):
        return False
    if isinstance(t, ListType):
        return equality_type(sigma, t.elem)
    if isinstance(t, DictType):
        return equality_type(sigma, t.value)
    if isinstance(t, TupleType):
        return all(equality_type(sigma, c) for c in t.components)
    if isinstance(t, UnionType):
        return equality_type(sigma, t.left) and equality_type(sigma, t.right)
    if isinstance(t, ClassType):
        return class_equality_type(sigma, t.c)
    return True


def class_equality_type(sigma: ClassTable, c: Class) -> bool:
    return all(
        equality_type(sigma, declared_type(sigma, c, x)) for x in fields(sigma, c)
    )


def membership_list(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if isinstance(t, ListType) and comparable(sigma, s, t.elem):
        return (s, t), Primitive.BOOL
    return None


def membership_tuple(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if isinstance(t, TupleType) and comparable(sigma, s, join(sigma, t.components)):
        return (s, t), Primitive.BOOL
    return None


def membership_str(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    return both(sigma, s, t, Primitive.STR, Primitive.BOOL)


def membership_dict(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if isinstance(t, DictType) and subtype(sigma, s, Primitive.STR):
        return (Primitive.STR, t), Primitive.BOOL
    return None


def ordering_number(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    return both(sigma, s, t, Primitive.FLOAT, Primitive.BOOL)


def ordering_str(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    return both(sigma, s, t, Primitive.STR, Primitive.BOOL)


def arithmetic_int(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    return both(sigma, s, t, Primitive.INT, Primitive.INT)


def arithmetic_float(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    return both(sigma, s, t, Primitive.FLOAT, Primitive.FLOAT)


def concat_str(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    return both(sigma, s, t, Primitive.STR, Primitive.STR)


def concat_list(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if isinstance(s, ListType) and isinstance(t, ListType):
        return (s, t), ListType(join(sigma, (s.elem, t.elem)))
    return None


def concat_tuple(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if isinstance(s, TupleType) and isinstance(t, TupleType):
        return (s, t), TupleType(s.components + t.components)
    return None


def repeat_str(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if subtype(sigma, s, Primitive.STR) and subtype(sigma, t, Primitive.INT):
        return (Primitive.STR, Primitive.INT), Primitive.STR
    return None


def repeat_str_left(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if subtype(sigma, s, Primitive.INT) and subtype(sigma, t, Primitive.STR):
        return (Primitive.INT, Primitive.STR), Primitive.STR
    return None


def repeat_list(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if isinstance(s, ListType) and subtype(sigma, t, Primitive.INT):
        return (s, Primitive.INT), s
    return None


def repeat_list_left(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if subtype(sigma, s, Primitive.INT) and isinstance(t, ListType):
        return (Primitive.INT, t), t
    return None


def power_int(sigma: ClassTable, s: Type, t: Type) -> ResolvedOverload | None:
    if subtype(sigma, s, Primitive.INT) and isinstance(t, LiteralType):
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


def negate_bool(sigma: ClassTable, s: Type) -> ResolvedOverload | None:
    return (
        ((Primitive.BOOL,), Primitive.BOOL)
        if subtype(sigma, s, Primitive.BOOL)
        else None
    )


def sign_int(sigma: ClassTable, s: Type) -> ResolvedOverload | None:
    return (
        ((Primitive.INT,), Primitive.INT) if subtype(sigma, s, Primitive.INT) else None
    )


def sign_float(sigma: ClassTable, s: Type) -> ResolvedOverload | None:
    return (
        ((Primitive.FLOAT,), Primitive.FLOAT)
        if subtype(sigma, s, Primitive.FLOAT)
        else None
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
    sigma: ClassTable, op: str, s: Type, t: Type
) -> list[ResolvedOverload]:
    candidates = [overload(sigma, s, t) for overload in BINARY_OVERLOADS[op]] + [
        overload(sigma, base_type(s), base_type(t)) for overload in BINARY_OVERLOADS[op]
    ]
    return list({resolved: None for resolved in candidates if resolved is not None})


def overloads_unary(sigma: ClassTable, op: str, s: Type) -> list[ResolvedOverload]:
    candidates = [overload(sigma, s) for overload in UNARY_OVERLOADS[op]] + [
        overload(sigma, base_type(s)) for overload in UNARY_OVERLOADS[op]
    ]
    return list({resolved: None for resolved in candidates if resolved is not None})


def minimum(
    sigma: ClassTable, resolved: Sequence[ResolvedOverload]
) -> ResolvedOverload | None:
    for candidate in resolved:
        if all(
            all(subtype(sigma, a, b) for a, b in zip(candidate[0], other[0]))
            for other in resolved
        ):
            return candidate
    return None
