from collections.abc import Sequence

from contexts import ModuleContext, ancestors
from type_syntax import (
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
    return False


def comparable(s: Type, t: Type, ctx: ModuleContext) -> bool:
    return subtype(s, t, ctx) or subtype(t, s, ctx)
