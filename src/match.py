"""How a pattern matches a shape, and how a shape splits for a pattern.

Matching a pattern against a shape gives the shapes it matches, the residual it
leaves and the bindings it makes, so a case that matches nothing has no
derivation and a match is exhaustive where the residual is empty. A shape which
stands for many heads splits first, into the shapes carrying the head the
pattern tests for and the shapes it leaves.
"""

import ast
from collections.abc import Callable, Iterable
from itertools import product

import reasons
from aux import qualified_name
from classes import Class, field_map, field_type, fields, short_name
from contexts import (
    ModuleContext,
    Status,
    VarContext,
    VarEntry,
    class_of_name,
)
from reasons import IllFormedModule
from shapes import (
    NOTHING,
    Constr,
    Dict,
    List,
    Literal,
    Rest,
    Seq,
    Shape,
    Tuple,
    below_excluded,
    head_typed,
    shape_type,
    shapes,
    shapes_seq,
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
type SeqMatch = tuple[frozenset[Seq], frozenset[Seq], VarContext]
type Split = tuple[frozenset[Shape], frozenset[Shape]]

NO_BINDINGS: VarContext = {}


def match(k: Shape, p: ast.pattern, ctx: ModuleContext) -> Match | None:
    """Shapes of `k` that `p` matches, the shapes it leaves and the bindings it
    makes, or nothing where `p` cannot match `k`."""
    if isinstance(p, ast.MatchAs):
        return match_as(k, p, ctx)
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        same = match_literal(k, LiteralType(literal_of(p)))
    elif isinstance(p, PatTuple):
        same = match_tuple(k, p, ctx)
    elif isinstance(p, PatList):
        same = match_list(k, p, ctx)
    elif isinstance(p, ast.MatchMapping):
        same = match_dict(k, p, ctx)
    else:
        assert isinstance(p, ast.MatchClass)
        same = match_constr(k, p, ctx)
    return same if same is not None else match_split(k, p, ctx)


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
    named = join([shape_type(m) for m in matched])
    return matched, left, disjoint_union([delta, {p.name: named}], p)


def match_split(k: Shape, p: ast.pattern, ctx: ModuleContext) -> Match | None:
    """The shapes the split gives, matched against the pattern, with the shapes
    the split leaves passed into the residual."""
    parts = split(k, p, ctx)
    if parts is None:
        return None
    ks, without = parts
    result = match_shapes(ks, p, ctx)
    if result is None:
        return None
    matched, left, delta = result
    return matched, left | without, delta


def match_literal(k: Shape, ell: LiteralType) -> Match | None:
    if isinstance(k, Literal) and LiteralType(k.value) == ell:
        return frozenset({k}), NOTHING, NO_BINDINGS
    return None


def match_tuple(k: Shape, p: PatTuple, ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    if isinstance(k, Tuple) and len(k.components) == len(ps):
        return wrap(Tuple, match_seq(k.components, ps, p, ctx))
    return None


def match_list(k: Shape, p: PatList, ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    if isinstance(k, List) and len(k.elems) == len(ps):
        return wrap(lambda r: List(k.elem, r), match_seq(k.elems, ps, p, ctx))
    return None


def match_dict(k: Shape, p: ast.MatchMapping, ctx: ModuleContext) -> Match | None:
    """Every key of the pattern is bound by the shape, so the keys match as a
    sequence."""
    if not isinstance(k, Dict):
        return None
    ws = items(p)
    keys = tuple(w for w, _ in ws)
    repeated = [w for i, w in enumerate(keys) if w in keys[:i]]
    if repeated:
        raise IllFormedModule(p, reasons.DuplicateDictKey(repeated[0]))
    bound = dict(k.bound)
    if any(w not in bound for w in keys):
        return None
    ks = tuple(bound[w] for w in keys)
    seqs = match_seq(ks, tuple(q for _, q in ws), p, ctx)
    return wrap(lambda r: with_keys(k, keys, r), seqs)


def match_constr(k: Shape, p: ast.MatchClass, ctx: ModuleContext) -> Match | None:
    cls = class_of_pattern(p, ctx)
    ps = pattern_seq(cls, p)
    if isinstance(k, Constr) and subtype(ClassType(k.c), ClassType(cls)):
        seqs = match_seq(k.args, padded(ps, len(k.args)), p, ctx)
        return wrap(lambda r: Constr(k.c, r, k.heads), seqs)
    return None


def split(k: Shape, p: ast.pattern, ctx: ModuleContext) -> Split | None:
    """Shapes of `k` carrying the head that `p` tests for, and the shapes `k`
    leaves without that head, or nothing where `k` does not split for `p`."""
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return split_literal(k, LiteralType(literal_of(p)), ctx)
    if isinstance(p, PatTuple):
        return split_tuple(k, len(p.patterns), ctx)
    if isinstance(p, PatList):
        return split_list(k, len(p.patterns), ctx)
    if isinstance(p, ast.MatchMapping):
        return split_key(k, items(p), ctx)
    assert isinstance(p, ast.MatchClass)
    cls = class_of_pattern(p, ctx)
    if isinstance(k, Rest):
        return split_class(k, cls, ctx)
    if isinstance(k, Constr):
        return split_subclass(k, cls, ctx)
    return None


def split_literal(k: Shape, ell: LiteralType, ctx: ModuleContext) -> Split | None:
    if isinstance(k, Rest) and ell not in k.heads and subtype(ell, k.ty):
        return frozenset({Literal(ell.value)}), shapes(k.ty, k.heads | {ell}, ctx)
    return None


def split_tuple(k: Shape, n: int, ctx: ModuleContext) -> Split | None:
    """No head types at a tuple type, so the shape excludes nothing and the
    split leaves nothing."""
    if not (isinstance(k, Rest) and isinstance(k.ty, TupleType)):
        return None
    if len(k.ty.components) != n:
        return None
    assert not k.heads
    return frozenset(Tuple(ks) for ks in shapes_seq(k.ty.components, ctx)), NOTHING


def split_list(k: Shape, n: int, ctx: ModuleContext) -> Split | None:
    if not (isinstance(k, Rest) and isinstance(k.ty, ListType) and n not in k.heads):
        return None
    elem = k.ty.elem
    return (
        frozenset(List(elem, ks) for ks in shapes_seq((elem,) * n, ctx)),
        shapes(k.ty, k.heads | {n}, ctx),
    )


def split_key(
    k: Shape, ws: tuple[tuple[str, ast.pattern], ...], ctx: ModuleContext
) -> Split | None:
    """The first key of the pattern which the shape does not bind."""
    if not isinstance(k, Dict):
        return None
    bound = dict(k.bound)
    w = next((w for w, _ in ws if w not in bound), None)
    if w is None or w in k.heads:
        return None
    return (
        frozenset(with_keys(k, (w,), (m,)) for m in shapes(k.value, frozenset(), ctx)),
        frozenset({Dict(k.value, k.bound, k.heads | {w})}),
    )


def split_class(k: Rest, cls: Class, ctx: ModuleContext) -> Split | None:
    """Instances of the lower of the shape's type and the pattern's class, with
    the heads which type at that class kept."""
    if not comparable(ClassType(cls), k.ty) or below_excluded(cls, k.heads, ctx):
        return None
    low = cls if subtype(ClassType(cls), k.ty) else class_of(k.ty)
    types = tuple(declared_field(low, x) for x in fields(low))
    kept = typed_heads(k.heads, ClassType(low), ctx)
    return (
        frozenset(Constr(low, ks, kept) for ks in shapes_seq(types, ctx)),
        shapes(k.ty, k.heads | {cls}, ctx),
    )


def split_subclass(k: Constr, cls: Class, ctx: ModuleContext) -> Split | None:
    """Instances of a proper subclass of the shape's class, whose fields are
    those of the shape followed by the ones the subclass declares."""
    if cls == k.c or not subtype(ClassType(cls), ClassType(k.c)):
        return None
    if below_excluded(cls, k.heads, ctx):
        return None
    own = tuple(declared_field(cls, x) for x in fields(cls)[len(k.args) :])
    kept = typed_heads(k.heads, ClassType(cls), ctx)
    return (
        frozenset(Constr(cls, k.args + ks, kept) for ks in shapes_seq(own, ctx)),
        frozenset({Constr(k.c, k.args, k.heads | {cls})}),
    )


def class_of_pattern(p: ast.MatchClass, ctx: ModuleContext) -> Class:
    """Class the pattern names."""
    cls = class_of_name(p.cls, ctx)
    if cls is None:
        raise IllFormedModule(p, reasons.UnknownClassInPattern(class_name(p.cls)))
    return cls


def pattern_seq(cls: Class, p: ast.MatchClass) -> tuple[ast.pattern, ...]:
    """Pattern the arguments supply for each field of `cls`, by field-map."""
    args = field_map(cls, p.patterns, p.kwd_attrs, p.kwd_patterns)
    if args is None:
        raise no_field_map(cls, p)
    return tuple(args[x] for x in fields(cls))


def typed_heads(
    heads: frozenset[object], t: Type, ctx: ModuleContext
) -> frozenset[object]:
    """The heads typed at `t`, kept when an excluded set passes to a shape of a
    narrower type."""
    return frozenset(h for h in heads if head_typed(h, t, ctx))


def class_of(t: Type) -> Class:
    assert isinstance(t, ClassType)
    return t.c


def match_seq(
    ks: Seq, ps: tuple[ast.pattern, ...], node: ast.pattern, ctx: ModuleContext
) -> SeqMatch | None:
    """Sequences that match the sequence of patterns, and sequences that fail at
    one position."""
    matches = [match(k, p, ctx) for k, p in zip(ks, ps)]
    if any(s is None for s in matches):
        return None
    parts = [s for s in matches if s is not None]
    matched = frozenset(product(*(m for m, _, _ in parts)))
    left = frozenset(
        tuple(prefix) + (k,) + ks[i + 1 :]
        for i, (_, ls, _) in enumerate(parts)
        for prefix in product(*(parts[j][0] for j in range(i)))
        for k in ls
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
    """Whether every sequence pattern within `p` meets only its own kind at
    type `t`."""
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
        cls = class_of_name(p.cls, ctx)
        if cls is None:
            return True  # the match rules reject with a sharper reason
        args = field_map(cls, p.patterns, p.kwd_attrs, p.kwd_patterns)
        if args is None:
            return True  # likewise
        return all(agrees(args[x], declared_field(cls, x), ctx) for x in fields(cls))
    if isinstance(p, ast.MatchAs):
        return p.pattern is None or agrees(p.pattern, t, ctx)
    return True


def declared_field(c: Class, x: str) -> Type:
    t = field_type(c, x)
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
    return join(types)


def ordered(ks: frozenset[Shape]) -> list[Shape]:
    """Shapes in a fixed order, so that a join over them does not depend on how
    the set happens to be iterated."""
    return sorted(ks, key=repr)


def union(sets: Iterable[frozenset[Shape]]) -> frozenset[Shape]:
    return frozenset(k for s in sets for k in s)


def wrap(form: Callable[[Seq], Shape], seqs: SeqMatch | None) -> Match | None:
    if seqs is None:
        return None
    matched, left, delta = seqs
    return (
        frozenset(form(ks) for ks in matched),
        frozenset(form(ks) for ks in left),
        delta,
    )


def padded(ps: tuple[ast.pattern, ...], n: int) -> tuple[ast.pattern, ...]:
    """Pattern sequence padded with wildcards, for a shape of a subclass whose
    extra fields the pattern does not name."""
    return ps + tuple(ast.MatchAs() for _ in range(n - len(ps)))


def class_name(cls: ast.expr) -> str:
    if isinstance(cls, (ast.Name, ast.Attribute)):
        return qualified_name(cls)
    return ast.unparse(cls)


def no_field_map(cls: Class, p: ast.MatchClass) -> IllFormedModule:
    """Why field-map is undefined for the pattern's arguments."""
    c, xs = short_name(cls), fields(cls)
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


def with_keys(k: Dict, ws: tuple[str, ...], ks: Seq) -> Dict:
    """Dictionary shape with each key of `ws` at the shape the sequence gives it."""
    bound = dict(k.bound) | dict(zip(ws, ks))
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
