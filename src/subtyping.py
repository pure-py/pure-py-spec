from collections.abc import Sequence

from contexts import ModuleContext, ancestors
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


def join_two(s: Type, t: Type, ctx: ModuleContext) -> Type:
    if subtype(s, t, ctx):
        return t
    if subtype(t, s, ctx):
        return s
    return UnionType(s, t)


def join(ts: Sequence[Type], ctx: ModuleContext) -> Type:
    if len(ts) == 0:
        return Primitive.NEVER
    return join_two(ts[0], join(ts[1:], ctx), ctx)


def subtype(s: Type, t: Type, ctx: ModuleContext) -> bool:
    if s == t or s == Primitive.NEVER or t == Primitive.OBJECT:
        return True
    if s == Primitive.INT and t == Primitive.FLOAT:
        return True
    if isinstance(s, LiteralType):
        return subtype(base_type(s.value), t, ctx)
    if isinstance(s, UnionType):
        return subtype(s.left, t, ctx) and subtype(s.right, t, ctx)
    if isinstance(t, UnionType):
        return subtype(s, t.left, ctx) or subtype(s, t.right, ctx)
    if t == Primitive.SIZED:
        return isinstance(s, (ListType, DictType, TupleType)) or s == Primitive.STR
    if isinstance(s, ClassType) and isinstance(t, ClassType):
        return t.entry in ancestors(s.entry)
    if isinstance(s, TupleType) and isinstance(t, TupleType):
        return len(s.components) == len(t.components) and all(
            subtype(a, b, ctx) for a, b in zip(s.components, t.components)
        )
    if isinstance(s, ListType) and isinstance(t, ListType):
        return equivalent(s.elem, t.elem, ctx)
    if isinstance(s, DictType) and isinstance(t, DictType):
        return equivalent(s.value, t.value, ctx)
    if isinstance(s, CallableType) and isinstance(t, CallableType):
        return (
            len(s.params) == len(t.params)
            and all(equivalent(a, b, ctx) for a, b in zip(s.params, t.params))
            and equivalent(s.result, t.result, ctx)
        )
    return False


def equivalent(s: Type, t: Type, ctx: ModuleContext) -> bool:
    """Each a subtype of the other."""
    return subtype(s, t, ctx) and subtype(t, s, ctx)


def comparable(s: Type, t: Type, ctx: ModuleContext) -> bool:
    return subtype(s, t, ctx) or subtype(t, s, ctx)
