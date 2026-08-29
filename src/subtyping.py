from collections.abc import Sequence

from contexts import ModuleContext, ancestors, class_of, short_name
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
        return isinstance(s, (ListType, DictType, TupleType)) or s in (
            Primitive.STR,
            Primitive.RANGE,
        )
    if isinstance(s, ClassType) and isinstance(t, ClassType):
        return t.q in ancestor_names(s.q, ctx)
    if isinstance(s, TupleType) and isinstance(t, TupleType):
        return len(s.components) == len(t.components) and all(
            subtype(a, b, ctx) for a, b in zip(s.components, t.components)
        )
    return False


def ancestor_names(q: str, ctx: ModuleContext) -> tuple[str, ...]:
    entry = class_of(ctx, q.rsplit(".", 1)[-1])
    return () if entry is None else tuple(short_name(a) for a in ancestors(entry))


def comparable(s: Type, t: Type, ctx: ModuleContext) -> bool:
    return subtype(s, t, ctx) or subtype(t, s, ctx)


def elem_type(t: Type, ctx: ModuleContext) -> Type | None:
    """Type of the elements a generator draws from a value of type `t`."""
    if isinstance(t, ListType):
        return t.elem
    if t == Primitive.STR:
        return Primitive.STR
    if t == Primitive.RANGE:
        return Primitive.INT
    if isinstance(t, DictType):
        return Primitive.STR
    if isinstance(t, TupleType):
        return join([base_type(c) for c in t.components], ctx)
    return None
