"""Shapes, and how a pattern splits them.

A shape denotes a set of values of a type. Splitting a shape by a pattern gives
the shapes the pattern matches, the residual it leaves and the bindings it
makes, so a case that matches nothing has no split and a match is exhaustive
where the residual is empty.
"""

import ast
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import product

from contexts import (
    ClassEntry,
    ModuleContext,
    Status,
    VarContext,
    VarEntry,
    class_entry,
    field_map,
    field_type,
    fields,
    short_name,
)
from patterns import dict_key, literal_of
from subtyping import comparable, join, subtype
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
    """Lists of element type `elem` whose entries have the given shapes."""

    elem: Type
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
type Split = tuple[frozenset[Shape], frozenset[Shape], VarContext]
type RowSplit = tuple[frozenset[Row], frozenset[Row], VarContext]

NOTHING: frozenset[Shape] = frozenset()
NO_BINDINGS: VarContext = {}


def shape_type(k: Shape) -> Type:
    """Least type of a shape."""
    if isinstance(k, Rest):
        return k.ty
    if isinstance(k, Literal):
        return LiteralType(k.value)
    if isinstance(k, Constr):
        return ClassType(k.q)
    if isinstance(k, Tuple):
        return TupleType(tuple(shape_type(c) for c in k.components))
    if isinstance(k, List):
        return ListType(k.elem)
    return DictType(k.value)


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


def split(k: Shape, p: ast.pattern, ctx: ModuleContext) -> Split | None:
    """Shapes of `k` that `p` matches, the shapes it leaves and the bindings it
    makes, or nothing where `p` cannot match `k`."""
    if isinstance(p, ast.MatchAs):
        return split_as(k, p, ctx)
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


def split_as(k: Shape, p: ast.MatchAs, ctx: ModuleContext) -> Split | None:
    """A variable or wildcard matches the whole shape; a named sub-pattern binds
    at the join over the shapes it matched."""
    if p.pattern is None:
        bare: VarContext = {} if p.name is None else {p.name: shape_type(k)}
        return frozenset({k}), NOTHING, bare
    result = split(k, p.pattern, ctx)
    if result is None:
        return None
    matched, left, delta = result
    if p.name is None:
        return matched, left, delta
    named = join([shape_type(m) for m in matched], ctx)
    return matched, left, disjoint_union([delta, {p.name: named}])


def split_literal(k: Shape, ell: LiteralType, ctx: ModuleContext) -> Split | None:
    if isinstance(k, Literal):
        if LiteralType(k.value) != ell:
            return None
        return frozenset({k}), NOTHING, NO_BINDINGS
    if isinstance(k, Rest) and ell not in k.heads and subtype(ell, k.ty, ctx):
        matched = frozenset({Literal(ell.value)})
        return matched, shapes(k.ty, k.heads | {ell}, ctx), NO_BINDINGS
    return None


def split_tuple(
    k: Shape, ps: tuple[ast.pattern, ...], ctx: ModuleContext
) -> Split | None:
    if isinstance(k, Tuple) and len(k.components) == len(ps):
        return wrap(Tuple, split_row(k.components, ps, ctx))
    if (
        isinstance(k, Rest)
        and isinstance(k.ty, TupleType)
        and len(k.ty.components) == len(ps)
    ):
        row = tuple(Rest(c, frozenset()) for c in k.ty.components)
        return wrap(Tuple, split_row(row, ps, ctx))
    return None


def split_list(
    k: Shape, ps: tuple[ast.pattern, ...], ctx: ModuleContext
) -> Split | None:
    n = len(ps)
    if isinstance(k, List) and len(k.elems) == n:
        return wrap(lambda r: List(k.elem, r), split_row(k.elems, ps, ctx))
    if isinstance(k, Rest) and isinstance(k.ty, ListType) and n not in k.heads:
        elem = k.ty.elem
        row = tuple(Rest(elem, frozenset()) for _ in ps)
        result = wrap(lambda r: List(elem, r), split_row(row, ps, ctx))
        if result is None:
            return None
        matched, left, delta = result
        return matched, left | shapes(k.ty, k.heads | {n}, ctx), delta
    return None


def split_constr(k: Shape, p: ast.MatchClass, ctx: ModuleContext) -> Split | None:
    entry = class_entry(p.cls, ctx)
    assert entry is not None
    q = short_name(entry)
    args = field_map(entry, p.patterns, p.kwd_attrs, p.kwd_patterns)
    assert args is not None
    ps = tuple(args[x] for x in fields(entry))
    if isinstance(k, Constr):
        if not subtype(ClassType(k.q), ClassType(q), ctx):
            return None
        rows = split_row(k.args, padded(ps, len(k.args)), ctx)
        return wrap(lambda r: Constr(k.q, r), rows)
    if isinstance(k, Rest) and q not in k.heads and comparable(ClassType(q), k.ty, ctx):
        row = tuple(field_shape(entry, x) for x in fields(entry))
        result = wrap(lambda r: Constr(q, r), split_row(row, ps, ctx))
        if result is None:
            return None
        matched, left, delta = result
        return matched, left | shapes(k.ty, k.heads | {q}, ctx), delta
    return None


def split_mapping(
    k: Shape, ws: tuple[tuple[str, ast.pattern], ...], ctx: ModuleContext
) -> Split | None:
    if not isinstance(k, Dict):
        return None
    if len(ws) == 0:
        return frozenset({k}), NOTHING, NO_BINDINGS
    (w, p), rest = ws[0], ws[1:]
    bound = dict(k.bound)
    if w in bound:
        first = split(bound[w], p, ctx)
    elif w not in k.heads:
        first = split_shapes(shapes(k.value, frozenset(), ctx), p, ctx)
    else:
        return None
    if first is None:
        return None
    matched, left, delta = first
    rest_split = split_mappings(
        frozenset(with_key(k, w, m) for m in matched), rest, ctx
    )
    if rest_split is None:
        return None
    matched_, left_, delta_ = rest_split
    absent = (
        NOTHING if w in bound else frozenset({Dict(k.value, k.bound, k.heads | {w})})
    )
    left__ = frozenset(with_key(k, w, r) for r in left) | left_ | absent
    return matched_, left__, disjoint_union([delta, delta_])


def split_mappings(
    ks: frozenset[Shape], ws: tuple[tuple[str, ast.pattern], ...], ctx: ModuleContext
) -> Split | None:
    splits = {k: s for k in ordered(ks) if (s := split_mapping(k, ws, ctx)) is not None}
    if len(splits) == 0:
        return None
    matched = union(m for m, _, _ in splits.values())
    left = union(left for _, left, _ in splits.values()) | (ks - splits.keys())
    return matched, left, join_deltas([d for _, _, d in splits.values()], ctx)


def split_row(
    row: Row, ps: tuple[ast.pattern, ...], ctx: ModuleContext
) -> RowSplit | None:
    """Rows that match the row of patterns, and rows that fail at one position."""
    splits = [split(k, p, ctx) for k, p in zip(row, ps)]
    if any(s is None for s in splits):
        return None
    parts = [s for s in splits if s is not None]
    matched = frozenset(product(*(m for m, _, _ in parts)))
    left = frozenset(
        tuple(prefix) + (k,) + row[i + 1 :]
        for i, (_, ks, _) in enumerate(parts)
        for prefix in product(*(parts[j][0] for j in range(i)))
        for k in ks
    )
    return matched, left, disjoint_union([d for _, _, d in parts])


def split_shapes(
    ks: frozenset[Shape], p: ast.pattern, ctx: ModuleContext
) -> Split | None:
    """Shapes of `ks` that `p` matches, with the shapes it does not match passed
    into the residual, or nothing where it matches none of them."""
    splits = {k: s for k in ordered(ks) if (s := split(k, p, ctx)) is not None}
    if len(splits) == 0:
        return None
    matched = union(m for m, _, _ in splits.values())
    left = union(left for _, left, _ in splits.values()) | (ks - splits.keys())
    return matched, left, join_deltas([d for _, _, d in splits.values()], ctx)


def disjoint_union(deltas: list[VarContext]) -> VarContext:
    """Bindings of sub-patterns taken together. Their variables are distinct,
    since a pattern is linear."""
    merged: VarContext = {}
    for delta in deltas:
        assert merged.keys().isdisjoint(delta.keys())
        merged = merged | delta
    return merged


def join_deltas(deltas: list[VarContext], ctx: ModuleContext) -> VarContext:
    """Bindings of a pattern that matches more than one shape, at the join of
    the types the shapes give each variable."""
    return {x: join_entries([d[x] for d in deltas], ctx) for x in deltas[0]}


def join_entries(entries: list[VarEntry], ctx: ModuleContext) -> VarEntry:
    types = [e for e in entries if not isinstance(e, Status)]
    return Status.TT if len(types) != len(entries) else join(types, ctx)


def ordered(ks: frozenset[Shape]) -> list[Shape]:
    """Shapes in a fixed order, so that a join over them does not depend on how
    the set happens to be iterated."""
    return sorted(ks, key=repr)


def union(sets: Iterable[frozenset[Shape]]) -> frozenset[Shape]:
    return frozenset(k for s in sets for k in s)


def wrap(form: Callable[[Row], Shape], rows: RowSplit | None) -> Split | None:
    if rows is None:
        return None
    matched, left, delta = rows
    return (
        frozenset(form(row) for row in matched),
        frozenset(form(row) for row in left),
        delta,
    )


def padded(ps: tuple[ast.pattern, ...], n: int) -> tuple[ast.pattern, ...]:
    """Pattern row padded with wildcards, for a shape of a subclass whose extra
    fields the pattern does not name."""
    return ps + tuple(ast.MatchAs() for _ in range(n - len(ps)))


def field_shape(entry: ClassEntry, x: str) -> Shape:
    """Shape of a field, with an unknown field type standing for any value."""
    t = field_type(entry, x)
    return Rest(Primitive.OBJECT if t is None else t, frozenset())


def with_key(k: Dict, w: str, m: Shape) -> Dict:
    bound = dict(k.bound) | {w: m}
    return Dict(k.value, tuple(sorted(bound.items())), k.heads)


def items(p: ast.MatchMapping) -> tuple[tuple[str, ast.pattern], ...]:
    return tuple(zip([dict_key(key) for key in p.keys], p.patterns))

