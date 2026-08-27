"""Residual coverage: what a sequence of patterns leaves unmatched.

A shape denotes a set of values. Subtracting a pattern from the residual gives what
remains; a pattern that removes nothing is unreachable, and a match is exhaustive
when the residual is empty.
"""

import ast
from dataclasses import dataclass
from itertools import product

from contexts import (
    ClassEntry,
    ModuleContext,
    ancestors,
    class_entry,
    field_map,
    fields,
    short_name,
)
from patterns import literal_value
from syntax import PatList, PatTuple
from type_syntax import (
    ClassType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    alts,
    base_type,
    subtype,
)


@dataclass(frozen=True)
class Any_:
    """Values of type `ty` whose head is none of `excluded`."""

    ty: Type
    excluded: frozenset[object]


@dataclass(frozen=True)
class Constr:
    cls: str
    args: tuple["Shape", ...]


@dataclass(frozen=True)
class Seq:
    kind: type[ast.pattern]
    args: tuple["Shape", ...]


@dataclass(frozen=True)
class Lit:
    value: object


type Shape = Any_ | Constr | Seq | Lit


def seed(t: Type) -> tuple[Shape, ...]:
    return tuple(Any_(m, frozenset()) for m in alts(t))


def is_empty(shapes: tuple[Shape, ...]) -> bool:
    return len(shapes) == 0


def strip(p: ast.pattern) -> ast.pattern:
    return strip(p.pattern) if isinstance(p, ast.MatchAs) and p.pattern else p


def irrefutable(p: ast.pattern) -> bool:
    return isinstance(p, ast.MatchAs) and p.pattern is None


def subtract(s: Shape, p: ast.pattern, ctx: ModuleContext) -> tuple[Shape, ...]:
    if irrefutable(p):
        return ()
    q = strip(p)
    if isinstance(q, (ast.MatchValue, ast.MatchSingleton)):
        return subtract_literal(s, literal_of(q), ctx)
    if isinstance(q, ast.MatchClass):
        return subtract_class(s, q, ctx)
    if isinstance(q, ast.MatchSequence):
        return subtract_sequence(s, q, ctx)
    return (s,)


def literal_of(p: ast.pattern) -> object:
    if isinstance(p, ast.MatchSingleton):
        return p.value
    assert isinstance(p, ast.MatchValue)
    return literal_value(p)


def subtract_literal(s: Shape, v: object, ctx: ModuleContext) -> tuple[Shape, ...]:
    if isinstance(s, Lit):
        return () if s.value == v else (s,)
    if isinstance(s, Any_) and subtype(LiteralType(v), s.ty, ctx):
        excluded = s.excluded | {v}
        return (
            ()
            if covers_all(s.ty, excluded, ctx)
            else (Any_(s.ty, frozenset(excluded)),)
        )
    return (s,)


def covers_all(t: Type, excluded: frozenset[object], ctx: ModuleContext) -> bool:
    """Whether the excluded literals exhaust the values of `t`."""
    if isinstance(t, LiteralType):
        return t.value in excluded
    if t == Primitive.BOOL:
        return {True, False} <= excluded
    if t == Primitive.NONE:
        return None in excluded
    return False


def subtract_class(
    s: Shape, p: ast.MatchClass, ctx: ModuleContext
) -> tuple[Shape, ...]:
    entry = class_entry(p.cls, ctx)
    if entry is None:
        return (s,)
    name = short_name(entry)
    args = field_map(entry, p.patterns, p.kwd_attrs, p.kwd_patterns)
    if args is None:
        return (s,)
    subs = tuple(args[x] for x in fields(entry))
    if isinstance(s, Constr):
        if not any(a.name == entry.name for a in ancestors_of(s.cls, ctx)):
            return (s,)
        return tuple(Constr(s.cls, row) for row in subtract_row(s.args, subs, ctx))
    if isinstance(s, Any_) and isinstance(s.ty, ClassType):
        if name in s.excluded:
            return (s,)
        below = subtype(s.ty, ClassType(name), ctx)
        shape = tuple(Any_(Primitive.OBJECT, frozenset()) for _ in subs)
        rest = tuple(Constr(name, row) for row in subtract_row(shape, subs, ctx))
        if below:
            return rest
        if subtype(ClassType(name), s.ty, ctx):
            return (Any_(s.ty, s.excluded | {name}),) + rest
    return (s,)


def ancestors_of(name: str, ctx: ModuleContext) -> tuple[ClassEntry, ...]:
    entry = class_entry(ast.Name(id=name), ctx)
    return () if entry is None else tuple(ancestors(entry))


def subtract_sequence(
    s: Shape, p: ast.MatchSequence, ctx: ModuleContext
) -> tuple[Shape, ...]:
    kind = PatList if isinstance(p, PatList) else PatTuple
    n = len(p.patterns)
    subs = tuple(p.patterns)
    if isinstance(s, Seq):
        if s.kind is not kind or len(s.args) != n:
            return (s,)
        return tuple(Seq(kind, row) for row in subtract_row(s.args, subs, ctx))
    if isinstance(s, Any_):
        if (
            kind is PatTuple
            and isinstance(s.ty, TupleType)
            and len(s.ty.components) == n
        ):
            row = tuple(Any_(t, frozenset()) for t in s.ty.components)
            return tuple(Seq(kind, r) for r in subtract_row(row, subs, ctx))
        if kind is PatList and isinstance(s.ty, ListType) and n not in s.excluded:
            row = tuple(Any_(s.ty.elem, frozenset()) for _ in range(n))
            rest = tuple(Seq(kind, r) for r in subtract_row(row, subs, ctx))
            return (Any_(s.ty, s.excluded | {n}),) + rest
    return (s,)


def subtract_row(
    row: tuple[Shape, ...], ps: tuple[ast.pattern, ...], ctx: ModuleContext
) -> tuple[tuple[Shape, ...], ...]:
    """Rows of shapes that fail to match the pattern row, one group per position."""
    out: list[tuple[Shape, ...]] = []
    for i, (s, p) in enumerate(zip(row, ps)):
        heads = [intersect(row[j], ps[j], ctx) for j in range(i)]
        if any(len(h) == 0 for h in heads):
            continue
        for prefix in product(*heads):
            out.extend(tuple(prefix) + (r,) + row[i + 1 :] for r in subtract(s, p, ctx))
    return tuple(out)


def intersect(s: Shape, p: ast.pattern, ctx: ModuleContext) -> tuple[Shape, ...]:
    if irrefutable(p):
        return (s,)
    q = strip(p)
    if isinstance(q, (ast.MatchValue, ast.MatchSingleton)):
        v = literal_of(q)
        if isinstance(s, Lit):
            return (s,) if s.value == v else ()
        if (
            isinstance(s, Any_)
            and subtype(base_type(v), s.ty, ctx)
            and v not in s.excluded
        ):
            return (Lit(v),)
        return ()
    return (s,)


def uncovered(
    t: Type, patterns: list[ast.pattern], ctx: ModuleContext
) -> tuple[tuple[Shape, ...], tuple[int, ...]]:
    """Residual after each pattern, and the indices of the unreachable ones."""
    residual = seed(t)
    unreachable: list[int] = []
    for i, p in enumerate(patterns):
        after = tuple(r for s in residual for r in subtract(s, p, ctx))
        if after == residual:
            unreachable.append(i)
        residual = after
    return residual, tuple(unreachable)
