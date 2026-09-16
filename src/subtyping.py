from collections.abc import Sequence

from classes import ClassTable, ancestors
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


def join(sigma: ClassTable, s: Type, t: Type) -> Type:
    if subtype(sigma, s, t):
        return t
    if subtype(sigma, t, s):
        return s
    return UnionType(s, t)


def meet(sigma: ClassTable, s: Type, t: Type) -> Type:
    if subtype(sigma, s, t):
        return s
    if subtype(sigma, t, s):
        return t
    if isinstance(s, UnionType):
        return join(sigma, meet(sigma, s.left, t), meet(sigma, s.right, t))
    if isinstance(t, UnionType):
        return join(sigma, meet(sigma, s, t.left), meet(sigma, s, t.right))
    if (
        isinstance(s, TupleType)
        and isinstance(t, TupleType)
        and len(s.components) == len(t.components)
    ):
        return TupleType(
            tuple(meet(sigma, a, b) for a, b in zip(s.components, t.components))
        )
    if (
        isinstance(s, CallableType)
        and isinstance(t, CallableType)
        and len(s.params) == len(t.params)
    ):
        return CallableType(
            tuple(join(sigma, a, b) for a, b in zip(s.params, t.params)),
            meet(sigma, s.result, t.result),
        )
    return Primitive.NEVER


def join_seq(sigma: ClassTable, ts: Sequence[Type]) -> Type:
    if len(ts) == 0:
        return Primitive.NEVER
    return join(sigma, ts[0], join_seq(sigma, ts[1:]))


def subtype(sigma: ClassTable, s: Type, t: Type) -> bool:
    if s == t or s == Primitive.NEVER or t == Primitive.OBJECT:
        return True
    if s == Primitive.INT and t == Primitive.FLOAT:
        return True
    if isinstance(s, UnionType):
        return subtype(sigma, s.left, t) and subtype(sigma, s.right, t)
    if isinstance(t, UnionType):
        return subtype(sigma, s, t.left) or subtype(sigma, s, t.right)
    if isinstance(s, LiteralType):
        return subtype(sigma, base_type(s.value), t)
    if t == Primitive.SIZED:
        return isinstance(s, (ListType, DictType, TupleType)) or s == Primitive.STR
    if isinstance(s, ClassType) and isinstance(t, ClassType):
        return t.c in ancestors(sigma, s.c)
    if isinstance(s, TupleType) and isinstance(t, TupleType):
        return len(s.components) == len(t.components) and all(
            subtype(sigma, a, b) for a, b in zip(s.components, t.components)
        )
    if isinstance(s, ListType) and isinstance(t, ListType):
        return equivalent(sigma, s.elem, t.elem)
    if isinstance(s, DictType) and isinstance(t, DictType):
        return equivalent(sigma, s.value, t.value)
    if isinstance(s, CallableType) and isinstance(t, CallableType):
        return (
            len(s.params) == len(t.params)
            and all(subtype(sigma, b, a) for a, b in zip(s.params, t.params))
            and subtype(sigma, s.result, t.result)
        )
    return False


def equivalent(sigma: ClassTable, s: Type, t: Type) -> bool:
    return subtype(sigma, s, t) and subtype(sigma, t, s)


def comparable(sigma: ClassTable, s: Type, t: Type) -> bool:
    return subtype(sigma, s, t) or subtype(sigma, t, s)
