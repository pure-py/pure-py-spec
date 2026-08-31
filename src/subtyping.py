from collections.abc import Sequence

from classes import ancestors
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


def join_two(s: Type, t: Type) -> Type:
    if subtype(s, t):
        return t
    if subtype(t, s):
        return s
    return UnionType(s, t)


def join(ts: Sequence[Type]) -> Type:
    if len(ts) == 0:
        return Primitive.NEVER
    return join_two(ts[0], join(ts[1:]))


def subtype(s: Type, t: Type) -> bool:
    if s == t or s == Primitive.NEVER or t == Primitive.OBJECT:
        return True
    if s == Primitive.INT and t == Primitive.FLOAT:
        return True
    if isinstance(s, UnionType):
        return subtype(s.left, t) and subtype(s.right, t)
    if isinstance(t, UnionType):
        return subtype(s, t.left) or subtype(s, t.right)
    if isinstance(s, LiteralType):
        return subtype(base_type(s.value), t)
    if t == Primitive.SIZED:
        return isinstance(s, (ListType, DictType, TupleType)) or s == Primitive.STR
    if isinstance(s, ClassType) and isinstance(t, ClassType):
        return t.c in ancestors(s.c)
    if isinstance(s, TupleType) and isinstance(t, TupleType):
        return len(s.components) == len(t.components) and all(
            subtype(a, b) for a, b in zip(s.components, t.components)
        )
    if isinstance(s, ListType) and isinstance(t, ListType):
        return equivalent(s.elem, t.elem)
    if isinstance(s, DictType) and isinstance(t, DictType):
        return equivalent(s.value, t.value)
    if isinstance(s, CallableType) and isinstance(t, CallableType):
        return (
            len(s.params) == len(t.params)
            and all(equivalent(a, b) for a, b in zip(s.params, t.params))
            and equivalent(s.result, t.result)
        )
    return False


def equivalent(s: Type, t: Type) -> bool:
    """Each a subtype of the other."""
    return subtype(s, t) and subtype(t, s)


def comparable(s: Type, t: Type) -> bool:
    return subtype(s, t) or subtype(t, s)
