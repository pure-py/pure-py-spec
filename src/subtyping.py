from collections.abc import Sequence

from contexts import ModuleContext, ancestors, class_of, short_name
from type_syntax import (
    ClassType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
    alts,
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
        return all(subtype(m, t, ctx) for m in alts(s))
    if isinstance(t, UnionType):
        return any(subtype(s, m, ctx) for m in alts(t))
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
