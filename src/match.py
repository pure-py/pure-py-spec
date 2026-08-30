"""How a pattern matches a shape.

Matching a pattern against a shape gives the shapes it matches, the residual it
leaves and the bindings it makes, so a case that matches nothing has no
derivation and a match is exhaustive where the residual is empty.
"""

import ast
from collections.abc import Callable, Iterable
from itertools import product

import reasons
from aux import qualified_name
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
from reasons import IllFormedModule
from shapes import (
    NOTHING,
    Constr,
    Dict,
    List,
    Literal,
    Rest,
    Row,
    Shape,
    Tuple,
    below_excluded,
    shape_type,
    shapes,
    shapes_row,
)
from subtyping import comparable, join, subtype
from syntax import PatList, PatTuple
from type_syntax import (
    ClassType,
    DictType,
    ListType,
    LiteralType,
    TupleType,
    Type,
    UnionType,
)

type Match = tuple[frozenset[Shape], frozenset[Shape], VarContext]
type RowMatch = tuple[frozenset[Row], frozenset[Row], VarContext]

NO_BINDINGS: VarContext = {}


def match(k: Shape, p: ast.pattern, ctx: ModuleContext) -> Match | None:
    """Shapes of `k` that `p` matches, the shapes it leaves and the bindings it
    makes, or nothing where `p` cannot match `k`."""
    if isinstance(p, ast.MatchAs):
        return match_as(k, p, ctx)
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return match_literal(k, LiteralType(literal_of(p)), ctx)
    if isinstance(p, PatTuple):
        return match_tuple(k, p, ctx)
    if isinstance(p, PatList):
        return match_list(k, p, ctx)
    if isinstance(p, ast.MatchMapping):
        return match_mapping(k, items(p), p, ctx)
    assert isinstance(p, ast.MatchClass)
    return match_constr(k, p, ctx)


def match_as(k: Shape, p: ast.MatchAs, ctx: ModuleContext) -> Match | None:
    """A variable or wildcard matches the whole shape; a named sub-pattern binds
    at the join over the shapes it matched."""
    if p.pattern is None:
        bare: VarContext = {} if p.name is None else {p.name: shape_type(k)}
        return frozenset({k}), NOTHING, bare
    result = match(k, p.pattern, ctx)
    if result is None:
        return None
    matched, left, delta = result
    if p.name is None:
        return matched, left, delta
    named = join([shape_type(m) for m in matched], ctx)
    return matched, left, disjoint_union([delta, {p.name: named}], p)


def match_literal(k: Shape, ell: LiteralType, ctx: ModuleContext) -> Match | None:
    if isinstance(k, Literal):
        if LiteralType(k.value) != ell:
            return None
        return frozenset({k}), NOTHING, NO_BINDINGS
    if isinstance(k, Rest) and ell not in k.heads and subtype(ell, k.ty, ctx):
        matched = frozenset({Literal(ell.value)})
        return matched, shapes(k.ty, k.heads | {ell}, ctx), NO_BINDINGS
    return None


def match_tuple(k: Shape, p: PatTuple, ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    if isinstance(k, Tuple) and len(k.components) == len(ps):
        return wrap(Tuple, match_row(k.components, ps, p, ctx))
    if (
        isinstance(k, Rest)
        and isinstance(k.ty, TupleType)
        and len(k.ty.components) == len(ps)
    ):
        expanded = frozenset(Tuple(row) for row in shapes_row(k.ty.components, ctx))
        return match_shapes(expanded, p, ctx)
    return None


def match_list(k: Shape, p: PatList, ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    n = len(ps)
    if isinstance(k, List) and len(k.elems) == n:
        return wrap(lambda r: List(k.elem, r), match_row(k.elems, ps, p, ctx))
    if isinstance(k, Rest) and isinstance(k.ty, ListType) and n not in k.heads:
        elem = k.ty.elem
        expanded = frozenset(List(elem, row) for row in shapes_row((elem,) * n, ctx))
        result = match_shapes(expanded, p, ctx)
        if result is None:
            return None
        matched, left, delta = result
        return matched, left | shapes(k.ty, k.heads | {n}, ctx), delta
    return None


def match_constr(k: Shape, p: ast.MatchClass, ctx: ModuleContext) -> Match | None:
    entry = class_entry(p.cls, ctx)
    if entry is None:
        raise IllFormedModule(p, reasons.UnknownClassInPattern(class_name(p.cls)))
    args = field_map(entry, p.patterns, p.kwd_attrs, p.kwd_patterns)
    if args is None:
        raise no_field_map(entry, p)
    ps = tuple(args[x] for x in fields(entry))
    if isinstance(k, Constr):
        if subtype(ClassType(k.entry), ClassType(entry), ctx):
            rows = match_row(k.args, padded(ps, len(k.args)), p, ctx)
            return wrap(lambda r: Constr(k.entry, r, k.heads), rows)
        if subtype(ClassType(entry), ClassType(k.entry), ctx) and not below_excluded(
            entry, k.heads, ctx
        ):
            own = tuple(declared_field(entry, x) for x in fields(entry)[len(k.args) :])
            kept = typed_heads(k.heads, ClassType(entry), ctx)
            expanded = frozenset(
                Constr(entry, k.args + row, kept) for row in shapes_row(own, ctx)
            )
            result = match_shapes(expanded, p, ctx)
            if result is None:
                return None
            matched, left, delta = result
            taken = Constr(k.entry, k.args, k.heads | {entry})
            return matched, left | {taken}, delta
        return None
    if (
        isinstance(k, Rest)
        and comparable(ClassType(entry), k.ty, ctx)
        and not below_excluded(entry, k.heads, ctx)
    ):
        low = entry if subtype(ClassType(entry), k.ty, ctx) else class_of(k.ty)
        types = tuple(declared_field(low, x) for x in fields(low))
        kept = typed_heads(k.heads, ClassType(low), ctx)
        expanded = frozenset(Constr(low, row, kept) for row in shapes_row(types, ctx))
        result = match_shapes(expanded, p, ctx)
        if result is None:
            return None
        matched, left, delta = result
        return matched, left | shapes(k.ty, k.heads | {entry}, ctx), delta
    return None


def typed_heads(
    heads: frozenset[object], t: Type, ctx: ModuleContext
) -> frozenset[object]:
    """The heads typed at `t`, kept when an excluded set passes to a shape of a
    narrower type."""
    return frozenset(h for h in heads if head_typed(h, t, ctx))


def class_of(t: Type) -> ClassEntry:
    assert isinstance(t, ClassType)
    return t.entry


def match_mapping(
    k: Shape,
    ws: tuple[tuple[str, ast.pattern], ...],
    node: ast.MatchMapping,
    ctx: ModuleContext,
) -> Match | None:
    if not isinstance(k, Dict):
        return None
    if len(ws) == 0:
        return frozenset({k}), NOTHING, NO_BINDINGS
    (w, p), rest = ws[0], ws[1:]
    if w in [key for key, _ in rest]:
        raise IllFormedModule(node, reasons.DuplicateDictKey(w))
    bound = dict(k.bound)
    if w in bound:
        first = match(bound[w], p, ctx)
    elif w not in k.heads:
        first = match_shapes(shapes(k.value, frozenset(), ctx), p, ctx)
    else:
        return None
    if first is None:
        return None
    matched, left, delta = first
    later = match_mappings(
        frozenset(with_key(k, w, m) for m in matched), rest, node, ctx
    )
    if later is None:
        return None
    matched_, left_, delta_ = later
    absent = (
        NOTHING if w in bound else frozenset({Dict(k.value, k.bound, k.heads | {w})})
    )
    left__ = frozenset(with_key(k, w, r) for r in left) | left_ | absent
    return matched_, left__, disjoint_union([delta, delta_], node)


def match_mappings(
    ks: frozenset[Shape],
    ws: tuple[tuple[str, ast.pattern], ...],
    node: ast.MatchMapping,
    ctx: ModuleContext,
) -> Match | None:
    matches = {
        k: s for k in ordered(ks) if (s := match_mapping(k, ws, node, ctx)) is not None
    }
    if len(matches) == 0:
        return None
    matched = union(m for m, _, _ in matches.values())
    left = union(left for _, left, _ in matches.values()) | (ks - matches.keys())
    return matched, left, join_deltas([d for _, _, d in matches.values()], ctx)


def match_row(
    row: Row, ps: tuple[ast.pattern, ...], node: ast.pattern, ctx: ModuleContext
) -> RowMatch | None:
    """Rows that match the row of patterns, and rows that fail at one position."""
    matches = [match(k, p, ctx) for k, p in zip(row, ps)]
    if any(s is None for s in matches):
        return None
    parts = [s for s in matches if s is not None]
    matched = frozenset(product(*(m for m, _, _ in parts)))
    left = frozenset(
        tuple(prefix) + (k,) + row[i + 1 :]
        for i, (_, ks, _) in enumerate(parts)
        for prefix in product(*(parts[j][0] for j in range(i)))
        for k in ks
    )
    return matched, left, disjoint_union([d for _, _, d in parts], node)


def match_shapes(
    ks: frozenset[Shape], p: ast.pattern, ctx: ModuleContext
) -> Match | None:
    """Shapes of `ks` that `p` matches, with the shapes it does not match passed
    into the residual, or nothing where it matches none of them."""
    matches = {k: s for k in ordered(ks) if (s := match(k, p, ctx)) is not None}
    if len(matches) == 0:
        return None
    matched = union(m for m, _, _ in matches.values())
    left = union(left for _, left, _ in matches.values()) | (ks - matches.keys())
    return matched, left, join_deltas([d for _, _, d in matches.values()], ctx)


def agrees(p: ast.pattern, t: Type, ctx: ModuleContext) -> bool:
    """True unless a sequence pattern within `p` would be matched against a
    value of the other kind at type `t`."""
    if isinstance(t, UnionType):
        return agrees(p, t.left, ctx) and agrees(p, t.right, ctx)
    if isinstance(p, PatTuple):
        if isinstance(t, ListType):
            return False
        if isinstance(t, TupleType) and len(t.components) == len(p.patterns):
            return all(agrees(q, c, ctx) for q, c in zip(p.patterns, t.components))
        return True
    if isinstance(p, PatList):
        if isinstance(t, TupleType):
            return False
        if isinstance(t, ListType):
            return all(agrees(q, t.elem, ctx) for q in p.patterns)
        return True
    if isinstance(p, ast.MatchMapping):
        if isinstance(t, DictType):
            return all(agrees(q, t.value, ctx) for q in p.patterns)
        return True
    if isinstance(p, ast.MatchClass):
        entry = class_entry(p.cls, ctx)
        if entry is None:
            return True
        args = field_map(entry, p.patterns, p.kwd_attrs, p.kwd_patterns)
        if args is None:
            return True
        return all(
            agrees(args[x], declared_field(entry, x), ctx) for x in fields(entry)
        )
    if isinstance(p, ast.MatchAs):
        return p.pattern is None or agrees(p.pattern, t, ctx)
    return True


def declared_field(entry: ClassEntry, x: str) -> Type:
    t = field_type(entry, x)
    assert t is not None
    return t


def disjoint_union(deltas: list[VarContext], node: ast.AST) -> VarContext:
    """Bindings of sub-patterns taken together, which compose only where the
    variables are distinct, so a pattern binding a name twice has no
    derivation."""
    merged: VarContext = {}
    for delta in deltas:
        repeated = sorted(merged.keys() & delta.keys())
        if repeated:
            raise IllFormedModule(node, reasons.NonlinearPattern(repeated[0]))
        merged = merged | delta
    return merged


def join_deltas(deltas: list[VarContext], ctx: ModuleContext) -> VarContext:
    """Bindings of a pattern that matches more than one shape, at the join of
    the types the shapes give each variable."""
    return {x: join_entries([d[x] for d in deltas], ctx) for x in deltas[0]}


def join_entries(entries: list[VarEntry], ctx: ModuleContext) -> VarEntry:
    """Bindings a pattern gives across the shapes it matches are all types, so
    they join."""
    types = [e for e in entries if not isinstance(e, Status)]
    assert len(types) == len(entries)
    return join(types, ctx)


def ordered(ks: frozenset[Shape]) -> list[Shape]:
    """Shapes in a fixed order, so that a join over them does not depend on how
    the set happens to be iterated."""
    return sorted(ks, key=repr)


def union(sets: Iterable[frozenset[Shape]]) -> frozenset[Shape]:
    return frozenset(k for s in sets for k in s)


def wrap(form: Callable[[Row], Shape], rows: RowMatch | None) -> Match | None:
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


def class_name(cls: ast.expr) -> str:
    if isinstance(cls, (ast.Name, ast.Attribute)):
        return qualified_name(cls)
    return ast.unparse(cls)


def no_field_map(entry: ClassEntry, p: ast.MatchClass) -> IllFormedModule:
    """Why field-map is undefined for the pattern's arguments."""
    c, xs = short_name(entry), fields(entry)
    n = len(p.patterns)
    if n + len(p.kwd_attrs) != len(xs):
        return IllFormedModule(
            p, reasons.PatternArityMismatch(c, len(xs), n + len(p.kwd_attrs))
        )
    if len(p.kwd_attrs) != len(set(p.kwd_attrs)):
        return IllFormedModule(p, reasons.DuplicatePatternKeyword(c))
    return IllFormedModule(
        p, reasons.UnknownFieldInPattern(c, tuple(sorted(set(xs[n:]))))
    )


def with_key(k: Dict, w: str, m: Shape) -> Dict:
    bound = dict(k.bound) | {w: m}
    return Dict(k.value, tuple(sorted(bound.items())), k.heads)


def items(p: ast.MatchMapping) -> tuple[tuple[str, ast.pattern], ...]:
    return tuple(zip([dict_key(key) for key in p.keys], p.patterns))


def literal_value(pat: ast.MatchValue) -> object:
    v = pat.value
    if isinstance(v, ast.Constant):
        return v.value
    if isinstance(v, ast.UnaryOp) and isinstance(v.operand, ast.Constant):
        operand_value = v.operand.value
        assert isinstance(operand_value, (int, float))
        return -operand_value if isinstance(v.op, ast.USub) else operand_value
    raise AssertionError(f"unexpected MatchValue payload: {type(v).__name__}")


def dict_key(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)
    return k.value


def literal_of(p: ast.pattern) -> object:
    if isinstance(p, ast.MatchSingleton):
        return p.value
    assert isinstance(p, ast.MatchValue)
    return literal_value(p)
