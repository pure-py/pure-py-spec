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
from subtyping import subtype
from syntax import PatList, PatTuple
from type_syntax import (
    ClassType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    alts,
)


@dataclass(frozen=True)
class Rest:
    """Values of type `ty` whose outermost constructor is none of `excluded`."""

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


type Shape = Rest | Constr | Seq | Lit


def seed(t: Type, ctx: ModuleContext) -> tuple[Shape, ...]:
    return tuple(k for m in alts(t) for k in rest(m, frozenset(), ctx))


def is_empty(shapes: tuple[Shape, ...]) -> bool:
    return len(shapes) == 0


def strip(p: ast.pattern) -> ast.pattern:
    return strip(p.pattern) if isinstance(p, ast.MatchAs) and p.pattern else p


def irrefutable(p: ast.pattern) -> bool:
    return isinstance(p, ast.MatchAs) and p.pattern is None


def split(
    s: Shape, p: ast.pattern, ctx: ModuleContext
) -> tuple[tuple[Shape, ...], tuple[Shape, ...]]:
    """The shapes of `s` that `p` matches, and the shapes it leaves."""
    if irrefutable(p):
        return (s,), ()
    q = strip(p)
    if isinstance(q, (ast.MatchValue, ast.MatchSingleton)):
        return split_literal(s, literal_of(q), ctx)
    if isinstance(q, ast.MatchClass):
        return split_class(s, q, ctx)
    if isinstance(q, ast.MatchSequence):
        return split_sequence(s, q, ctx)
    return (), (s,)


def literal_of(p: ast.pattern) -> object:
    if isinstance(p, ast.MatchSingleton):
        return p.value
    assert isinstance(p, ast.MatchValue)
    return literal_value(p)


def split_literal(
    s: Shape, v: object, ctx: ModuleContext
) -> tuple[tuple[Shape, ...], tuple[Shape, ...]]:
    if isinstance(s, Lit):
        return ((s,), ()) if s.value == v else ((), (s,))
    if (
        isinstance(s, Rest)
        and v not in s.excluded
        and subtype(LiteralType(v), s.ty, ctx)
    ):
        return (Lit(v),), rest(s.ty, s.excluded | {v}, ctx)
    return (), (s,)


def covers(excluded: frozenset[object], t: Type, ctx: ModuleContext) -> bool:
    """Whether the excluded constructors leave no values of `t`."""
    if isinstance(t, LiteralType):
        return t.value in excluded
    if isinstance(t, ClassType):
        return any(
            isinstance(q, str) and subtype(t, ClassType(q), ctx) for q in excluded
        )
    if t == Primitive.BOOL:
        return {True, False} <= excluded
    if t == Primitive.NONE:
        return None in excluded
    return t == Primitive.NEVER


def rest(t: Type, excluded: frozenset[object], ctx: ModuleContext) -> tuple[Shape, ...]:
    return () if covers(excluded, t, ctx) else (Rest(t, excluded),)


def split_class(
    s: Shape, p: ast.MatchClass, ctx: ModuleContext
) -> tuple[tuple[Shape, ...], tuple[Shape, ...]]:
    entry = class_entry(p.cls, ctx)
    if entry is None:
        return (), (s,)
    name = short_name(entry)
    args = field_map(entry, p.patterns, p.kwd_attrs, p.kwd_patterns)
    if args is None:
        return (), (s,)
    subs = tuple(args[x] for x in fields(entry))
    if isinstance(s, Constr):
        if not any(a.name == entry.name for a in ancestors_of(s.cls, ctx)):
            return (), (s,)
        matched, remaining = split_row(s.args, subs, ctx)
        return (
            tuple(Constr(s.cls, row) for row in matched),
            tuple(Constr(s.cls, row) for row in remaining),
        )
    if isinstance(s, Rest) and isinstance(s.ty, ClassType) and name not in s.excluded:
        cls = ClassType(name)
        if not (subtype(s.ty, cls, ctx) or subtype(cls, s.ty, ctx)):
            return (), (s,)
        row = tuple(Rest(Primitive.OBJECT, frozenset()) for _ in subs)
        matched, remaining = split_row(row, subs, ctx)
        return (
            tuple(Constr(name, r) for r in matched),
            tuple(Constr(name, r) for r in remaining)
            + rest(s.ty, s.excluded | {name}, ctx),
        )
    return (), (s,)


def ancestors_of(name: str, ctx: ModuleContext) -> tuple[ClassEntry, ...]:
    entry = class_entry(ast.Name(id=name), ctx)
    return () if entry is None else tuple(ancestors(entry))


def split_sequence(
    s: Shape, p: ast.MatchSequence, ctx: ModuleContext
) -> tuple[tuple[Shape, ...], tuple[Shape, ...]]:
    kind = PatList if isinstance(p, PatList) else PatTuple
    n = len(p.patterns)
    subs = tuple(p.patterns)
    if isinstance(s, Seq):
        if s.kind is not kind or len(s.args) != n:
            return (), (s,)
        matched, remaining = split_row(s.args, subs, ctx)
        return (
            tuple(Seq(kind, r) for r in matched),
            tuple(Seq(kind, r) for r in remaining),
        )
    if isinstance(s, Rest):
        if (
            kind is PatTuple
            and isinstance(s.ty, TupleType)
            and len(s.ty.components) == n
        ):
            row = tuple(Rest(t, frozenset()) for t in s.ty.components)
            matched, remaining = split_row(row, subs, ctx)
            return (
                tuple(Seq(kind, r) for r in matched),
                tuple(Seq(kind, r) for r in remaining),
            )
        if kind is PatList and isinstance(s.ty, ListType) and n not in s.excluded:
            row = tuple(Rest(s.ty.elem, frozenset()) for _ in range(n))
            matched, remaining = split_row(row, subs, ctx)
            return (
                tuple(Seq(kind, r) for r in matched),
                tuple(Seq(kind, r) for r in remaining)
                + rest(s.ty, s.excluded | {n}, ctx),
            )
    return (), (s,)


type Row = tuple[Shape, ...]


def split_row(
    row: Row, ps: tuple[ast.pattern, ...], ctx: ModuleContext
) -> tuple[tuple[Row, ...], tuple[Row, ...]]:
    """Rows that match the pattern row, and rows that fail at some position."""
    splits = [split(s, p, ctx) for s, p in zip(row, ps)]
    matched = tuple(product(*(m for m, _ in splits)))
    rest = tuple(
        tuple(prefix) + (r,) + row[i + 1 :]
        for i, (_, ks) in enumerate(splits)
        for prefix in product(*(splits[j][0] for j in range(i)))
        for r in ks
    )
    return matched, rest


def split_set(
    shapes: tuple[Shape, ...], p: ast.pattern, ctx: ModuleContext
) -> tuple[tuple[Shape, ...], tuple[Shape, ...]]:
    splits = [split(s, p, ctx) for s in shapes]
    return (
        tuple(k for m, _ in splits for k in m),
        tuple(k for _, ks in splits for k in ks),
    )


def uncovered(
    t: Type, patterns: list[ast.pattern], ctx: ModuleContext
) -> tuple[tuple[Shape, ...], tuple[int, ...]]:
    """The residual after every pattern, and the indices of the unreachable ones."""
    residual = seed(t, ctx)
    unreachable: list[int] = []
    for i, p in enumerate(patterns):
        matched, residual = split_set(residual, p, ctx)
        if len(matched) == 0:
            unreachable.append(i)
    return residual, tuple(unreachable)
