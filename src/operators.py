import ast
from collections.abc import Callable, Sequence

from classes import Class, ClassTable, declared_type, fields
from subtyping import comparable, join_seq, subtype
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
    Sigma: ClassTable, sigma: Type, tau: Type, bound: Type, result: Type
) -> ResolvedOverload | None:
    return (
        ((bound, bound), result)
        if subtype(Sigma, sigma, bound) and subtype(Sigma, tau, bound)
        else None
    )


def equality(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if not comparable(Sigma, sigma, tau):
        return None
    if not equality_type(Sigma, sigma) or not equality_type(Sigma, tau):
        return None
    return (sigma, tau), Primitive.BOOL


def equality_type(Sigma: ClassTable, tau: Type) -> bool:
    match tau:
        case CallableType():
            return False
        case ListType(sigma):
            return equality_type(Sigma, sigma)
        case DictType(sigma):
            return equality_type(Sigma, sigma)
        case TupleType(taus):
            return all(equality_type(Sigma, c) for c in taus)
        case UnionType(sigma, tau_):
            return equality_type(Sigma, sigma) and equality_type(Sigma, tau_)
        case ClassType(c):
            return class_equality_type(Sigma, c)
        case Primitive():
            return True
        case LiteralType():
            return True


def class_equality_type(Sigma: ClassTable, c: Class) -> bool:
    return all(equality_type(Sigma, declared_type(Sigma, c, x)) for x in fields(Sigma, c))


def membership_list(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if isinstance(tau, ListType) and comparable(Sigma, sigma, tau.elem):
        return (sigma, tau), Primitive.BOOL
    return None


def membership_tuple(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if isinstance(tau, TupleType) and comparable(Sigma, sigma, join_seq(Sigma, tau.components)):
        return (sigma, tau), Primitive.BOOL
    return None


def membership_str(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    return both(Sigma, sigma, tau, Primitive.STR, Primitive.BOOL)


def membership_dict(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if isinstance(tau, DictType) and subtype(Sigma, sigma, Primitive.STR):
        return (Primitive.STR, tau), Primitive.BOOL
    return None


def ordering_number(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    return both(Sigma, sigma, tau, Primitive.FLOAT, Primitive.BOOL)


def ordering_str(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    return both(Sigma, sigma, tau, Primitive.STR, Primitive.BOOL)


def arithmetic_int(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    return both(Sigma, sigma, tau, Primitive.INT, Primitive.INT)


def arithmetic_float(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    return both(Sigma, sigma, tau, Primitive.FLOAT, Primitive.FLOAT)


def concat_str(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    return both(Sigma, sigma, tau, Primitive.STR, Primitive.STR)


def concat_list(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if isinstance(sigma, ListType) and isinstance(tau, ListType):
        return (sigma, tau), ListType(join_seq(Sigma, (sigma.elem, tau.elem)))
    return None


def concat_tuple(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if isinstance(sigma, TupleType) and isinstance(tau, TupleType):
        return (sigma, tau), TupleType(sigma.components + tau.components)
    return None


def repeat_str(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if subtype(Sigma, sigma, Primitive.STR) and subtype(Sigma, tau, Primitive.INT):
        return (Primitive.STR, Primitive.INT), Primitive.STR
    return None


def repeat_str_left(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if subtype(Sigma, sigma, Primitive.INT) and subtype(Sigma, tau, Primitive.STR):
        return (Primitive.INT, Primitive.STR), Primitive.STR
    return None


def repeat_list(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if isinstance(sigma, ListType) and subtype(Sigma, tau, Primitive.INT):
        return (sigma, Primitive.INT), sigma
    return None


def repeat_list_left(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if subtype(Sigma, sigma, Primitive.INT) and isinstance(tau, ListType):
        return (Primitive.INT, tau), tau
    return None


def power_int(Sigma: ClassTable, sigma: Type, tau: Type) -> ResolvedOverload | None:
    if subtype(Sigma, sigma, Primitive.INT) and isinstance(tau, LiteralType):
        exponent = tau.ell.value
        if isinstance(exponent, int) and not isinstance(exponent, bool):
            return (Primitive.INT, tau), (Primitive.FLOAT if exponent < 0 else Primitive.INT)
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


def negate_bool(Sigma: ClassTable, sigma: Type) -> ResolvedOverload | None:
    return ((Primitive.BOOL,), Primitive.BOOL) if subtype(Sigma, sigma, Primitive.BOOL) else None


def sign_int(Sigma: ClassTable, sigma: Type) -> ResolvedOverload | None:
    return ((Primitive.INT,), Primitive.INT) if subtype(Sigma, sigma, Primitive.INT) else None


def sign_float(Sigma: ClassTable, sigma: Type) -> ResolvedOverload | None:
    return ((Primitive.FLOAT,), Primitive.FLOAT) if subtype(Sigma, sigma, Primitive.FLOAT) else None


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


def overloads_binary(Sigma: ClassTable, op: str, sigma: Type, tau: Type) -> list[ResolvedOverload]:
    candidates = [overload(Sigma, sigma, tau) for overload in BINARY_OVERLOADS[op]] + [
        overload(Sigma, base_type(sigma), base_type(tau)) for overload in BINARY_OVERLOADS[op]
    ]
    return list({resolved: None for resolved in candidates if resolved is not None})


def overloads_unary(Sigma: ClassTable, op: str, sigma: Type) -> list[ResolvedOverload]:
    candidates = [overload(Sigma, sigma) for overload in UNARY_OVERLOADS[op]] + [
        overload(Sigma, base_type(sigma)) for overload in UNARY_OVERLOADS[op]
    ]
    return list({resolved: None for resolved in candidates if resolved is not None})


def resolve_op_binary(Sigma: ClassTable, op: str, sigma: Type, tau: Type) -> Type | None:
    least = minimum(Sigma, overloads_binary(Sigma, op, sigma, tau))
    return None if least is None else least[1]


def resolve_op_unary(Sigma: ClassTable, op: str, sigma: Type) -> Type | None:
    least = minimum(Sigma, overloads_unary(Sigma, op, sigma))
    return None if least is None else least[1]


def minimum(Sigma: ClassTable, resolved: Sequence[ResolvedOverload]) -> ResolvedOverload | None:
    for candidate in resolved:
        if all(
            all(subtype(Sigma, a, b) for a, b in zip(candidate[0], other[0])) for other in resolved
        ):
            return candidate
    return None
