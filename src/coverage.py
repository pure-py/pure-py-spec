"""Shapes, and how a pattern splits them.

A shape denotes a set of values of a type. Splitting a shape by a pattern gives
the shapes the pattern matches and the residual it leaves, so a case that
matches nothing is unreachable and a match is exhaustive where the residual is
empty.
"""

import ast
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import product

from contexts import (
    ClassEntry,
    ModuleContext,
    class_entry,
    field_map,
    field_type,
    fields,
    short_name,
)
from patterns import dict_key, literal_value
from subtyping import comparable, subtype
from syntax import PatList, PatTuple
from type_syntax import (
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
)


@dataclass(frozen=True)
class Rest:
    """Values of type `ty` whose head is not among `heads`."""

    ty: Type
    heads: frozenset[object]


@dataclass(frozen=True)
class Literal:
    value: object


@dataclass(frozen=True)
class Constr:
    q: str
    args: tuple["Shape", ...]


@dataclass(frozen=True)
class Tuple:
    components: tuple["Shape", ...]


@dataclass(frozen=True)
class List:
    elems: tuple["Shape", ...]


@dataclass(frozen=True)
class Dict:
    """Dictionaries holding each key of `bound` with the shape it gives, and no
    key of `heads`."""

    value: Type
    bound: tuple[tuple[str, "Shape"], ...]
    heads: frozenset[str]


type Shape = Rest | Literal | Constr | Tuple | List | Dict
type Row = tuple[Shape, ...]
type Split = tuple[frozenset[Shape], frozenset[Shape]]

NOTHING: frozenset[Shape] = frozenset()


def shapes(t: Type, heads: frozenset[object], ctx: ModuleContext) -> frozenset[Shape]:
    """Shapes of `t` that remain once the heads in `heads` are excluded."""
    if isinstance(t, UnionType):
        return shapes(t.left, heads, ctx) | shapes(t.right, heads, ctx)
    if isinstance(t, LiteralType) and t in heads:
        return NOTHING
    if t == Primitive.BOOL and {LiteralType(True), LiteralType(False)} <= heads:
        return NOTHING
    if t == Primitive.NONE and LiteralType(None) in heads:
        return NOTHING
    if isinstance(t, ClassType) and any(
        isinstance(h, str) and subtype(t, ClassType(h), ctx) for h in heads
    ):
        return NOTHING
    if t == Primitive.NEVER:
        return NOTHING
    if isinstance(t, DictType):
        return frozenset(
            {Dict(t.value, (), frozenset(k for k in heads if isinstance(k, str)))}
        )
    return frozenset({Rest(t, heads)})


def split(k: Shape, p: ast.pattern, ctx: ModuleContext) -> Split:
    """Shapes of `k` that `p` matches, and the shapes it leaves."""
    if isinstance(p, ast.MatchAs):
        return (
            (frozenset({k}), NOTHING) if p.pattern is None else split(k, p.pattern, ctx)
        )
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return split_literal(k, LiteralType(literal_of(p)), ctx)
    if isinstance(p, PatTuple):
        return split_tuple(k, tuple(p.patterns), ctx)
    if isinstance(p, PatList):
        return split_list(k, tuple(p.patterns), ctx)
    if isinstance(p, ast.MatchMapping):
        return split_mapping(k, items(p), ctx)
    assert isinstance(p, ast.MatchClass)
    return split_constr(k, p, ctx)


def split_literal(k: Shape, ell: LiteralType, ctx: ModuleContext) -> Split:
    if isinstance(k, Literal):
        return (
            (frozenset({k}), NOTHING)
            if LiteralType(k.value) == ell
            else (NOTHING, frozenset({k}))
        )
    if isinstance(k, Rest) and ell not in k.heads and subtype(ell, k.ty, ctx):
        return frozenset({Literal(ell.value)}), shapes(k.ty, k.heads | {ell}, ctx)
    return NOTHING, frozenset({k})


def split_tuple(k: Shape, ps: tuple[ast.pattern, ...], ctx: ModuleContext) -> Split:
    if isinstance(k, Tuple) and len(k.components) == len(ps):
        return wrap(Tuple, split_row(k.components, ps, ctx))
    if (
        isinstance(k, Rest)
        and isinstance(k.ty, TupleType)
        and len(k.ty.components) == len(ps)
    ):
        row = tuple(Rest(c, frozenset()) for c in k.ty.components)
        return wrap(Tuple, split_row(row, ps, ctx))
    return NOTHING, frozenset({k})


def split_list(k: Shape, ps: tuple[ast.pattern, ...], ctx: ModuleContext) -> Split:
    n = len(ps)
    if isinstance(k, List) and len(k.elems) == n:
        return wrap(List, split_row(k.elems, ps, ctx))
    if isinstance(k, Rest) and isinstance(k.ty, ListType) and n not in k.heads:
        row = tuple(Rest(k.ty.elem, frozenset()) for _ in ps)
        matched, left = wrap(List, split_row(row, ps, ctx))
        return matched, left | shapes(k.ty, k.heads | {n}, ctx)
    return NOTHING, frozenset({k})


def split_constr(k: Shape, p: ast.MatchClass, ctx: ModuleContext) -> Split:
    entry = class_entry(p.cls, ctx)
    assert entry is not None
    q = short_name(entry)
    args = field_map(entry, p.patterns, p.kwd_attrs, p.kwd_patterns)
    assert args is not None
    ps = tuple(args[x] for x in fields(entry))
    if isinstance(k, Constr):
        if not subtype(ClassType(k.q), ClassType(q), ctx):
            return NOTHING, frozenset({k})
        return wrap(lambda row: Constr(k.q, row), split_row(k.args, ps, ctx))
    if isinstance(k, Rest) and q not in k.heads and comparable(ClassType(q), k.ty, ctx):
        row = tuple(field_shape(entry, x) for x in fields(entry))
        matched, left = wrap(lambda r: Constr(q, r), split_row(row, ps, ctx))
        return matched, left | shapes(k.ty, k.heads | {q}, ctx)
    return NOTHING, frozenset({k})


def split_mapping(
    k: Shape, ws: tuple[tuple[str, ast.pattern], ...], ctx: ModuleContext
) -> Split:
    if not isinstance(k, Dict):
        return NOTHING, frozenset({k})
    if len(ws) == 0:
        return frozenset({k}), NOTHING
    (w, p), rest = ws[0], ws[1:]
    bound = dict(k.bound)
    if w in bound:
        matched, left = split(bound[w], p, ctx)
    elif w not in k.heads:
        matched, left = split_shapes(shapes(k.value, frozenset(), ctx), p, ctx)
    else:
        return NOTHING, frozenset({k})
    matched_, left_ = split_mappings(
        frozenset(with_key(k, w, m) for m in matched), rest, ctx
    )
    absent = (
        NOTHING if w in bound else frozenset({Dict(k.value, k.bound, k.heads | {w})})
    )
    return matched_, frozenset(with_key(k, w, r) for r in left) | left_ | absent


def split_mappings(
    ks: frozenset[Shape], ws: tuple[tuple[str, ast.pattern], ...], ctx: ModuleContext
) -> Split:
    splits = [split_mapping(k, ws, ctx) for k in ks]
    return union(m for m, _ in splits), union(left for _, left in splits)


def split_row(
    row: Row, ps: tuple[ast.pattern, ...], ctx: ModuleContext
) -> tuple[frozenset[Row], frozenset[Row]]:
    """Rows that match the row of patterns, and rows that fail at one position."""
    splits = [split(k, p, ctx) for k, p in zip(row, ps)]
    matched = frozenset(product(*(m for m, _ in splits)))
    left = frozenset(
        tuple(prefix) + (k,) + row[i + 1 :]
        for i, (_, ks) in enumerate(splits)
        for prefix in product(*(splits[j][0] for j in range(i)))
        for k in ks
    )
    return matched, left


def split_shapes(ks: frozenset[Shape], p: ast.pattern, ctx: ModuleContext) -> Split:
    splits = [split(k, p, ctx) for k in ks]
    return union(m for m, _ in splits), union(left for _, left in splits)


def union(sets: Iterable[frozenset[Shape]]) -> frozenset[Shape]:
    return frozenset(k for s in sets for k in s)


def wrap(
    form: Callable[[Row], Shape], rows: tuple[frozenset[Row], frozenset[Row]]
) -> Split:
    matched, left = rows
    return frozenset(form(row) for row in matched), frozenset(form(row) for row in left)


def field_shape(entry: ClassEntry, x: str) -> Shape:
    """Shape of a field, with an unknown field type standing for any value."""
    t = field_type(entry, x)
    return Rest(Primitive.OBJECT if t is None else t, frozenset())


def with_key(k: Dict, w: str, m: Shape) -> Dict:
    bound = dict(k.bound) | {w: m}
    return Dict(k.value, tuple(sorted(bound.items())), k.heads)


def items(p: ast.MatchMapping) -> tuple[tuple[str, ast.pattern], ...]:
    return tuple(zip([dict_key(key) for key in p.keys], p.patterns))


def literal_of(p: ast.pattern) -> object:
    if isinstance(p, ast.MatchSingleton):
        return p.value
    assert isinstance(p, ast.MatchValue)
    return literal_value(p)
