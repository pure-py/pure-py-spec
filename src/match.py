import ast
from collections.abc import Callable, Iterable
from itertools import product

import reasons
from aux import qualified_name
from classes import Class, ClassTable, declared_type, field_map, fields, short_name
from contexts import (
    ModuleContext,
    VarContext,
    class_of_name,
    disjoint_union,
    join_context,
)
from reasons import IllFormedModule
from shapes import (
    Constr,
    Dict,
    List,
    Rest,
    Seq,
    Shape,
    Tuple,
    below_excluded,
    shape_type,
    shapes,
    shapes_seq,
    typed_heads,
)
from subtyping import join_seq, meet, subtype
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
    literal_type,
)

type Match = tuple[tuple[Shape, ...], tuple[Shape, ...], VarContext]
type SeqMatch = tuple[tuple[Seq, ...], tuple[Seq, ...], VarContext]
type Split = tuple[tuple[Shape, ...], tuple[Shape, ...]]


def match(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
    if isinstance(p, ast.MatchAs):
        return match_as(k, p, mod_ctx)
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        same = match_literal(k, literal_of(p))
    elif isinstance(p, PatTuple):
        same = match_tuple(k, p, mod_ctx)
    elif isinstance(p, PatList):
        same = match_list(k, p, mod_ctx)
    elif isinstance(p, ast.MatchMapping):
        same = match_dict(k, p, mod_ctx)
    else:
        assert isinstance(p, ast.MatchClass)
        same = match_constr(k, p, mod_ctx)
    return same if same is not None else match_split(k, p, mod_ctx)


def match_as(k: Shape, p: ast.MatchAs, mod_ctx: ModuleContext) -> Match | None:
    if p.pattern is None:
        bare: VarContext = {} if p.name is None else {p.name: shape_type(k)}
        return (k,), (), bare
    result = match(k, p.pattern, mod_ctx)
    if result is None:
        return None
    matched, residual, delta = result
    if p.name is None:
        return matched, residual, delta
    named = join_seq(mod_ctx.sigma, [shape_type(m) for m in matched])
    return matched, residual, pattern_bindings([delta, {p.name: named}], p)


def match_split(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
    parts = split(k, p, mod_ctx)
    if parts is None:
        return None
    ks, residual = parts
    result = match_shapes(ks, p, mod_ctx)
    if result is None:
        return None
    matched, residual_, delta = result
    return matched, residual + residual_, delta


def match_literal(k: Shape, ell: LiteralType) -> Match | None:
    if isinstance(k, Rest) and k.ty == ell:
        assert not k.heads
        return (k,), (), {}
    return None


def match_tuple(k: Shape, p: PatTuple, mod_ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    if isinstance(k, Tuple) and len(k.components) == len(ps):
        return map_seq_match(Tuple, match_seq(k.components, ps, p, mod_ctx))
    return None


def match_list(k: Shape, p: PatList, mod_ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    if isinstance(k, List) and len(k.elems) == len(ps):
        return map_seq_match(
            lambda r: List(k.elem, r), match_seq(k.elems, ps, p, mod_ctx)
        )
    return None


def match_dict(k: Shape, p: ast.MatchMapping, mod_ctx: ModuleContext) -> Match | None:
    if not isinstance(k, Dict):
        return None
    ws = key_patterns(p)
    keys = tuple(w for w, _ in ws)
    repeated = [w for i, w in enumerate(keys) if w in keys[:i]]
    if len(repeated) > 0:
        raise IllFormedModule(p, reasons.DuplicateDictKey(repeated[0]))
    bound = dict(k.bound)
    if any(w not in bound for w in keys):
        return None
    ks = tuple(bound[w] for w in keys)
    seqs = match_seq(ks, tuple(q for _, q in ws), p, mod_ctx)
    return map_seq_match(lambda r: with_keys(k, keys, r), seqs)


def match_constr(k: Shape, p: ast.MatchClass, mod_ctx: ModuleContext) -> Match | None:
    cls = class_of_pattern(p, mod_ctx)
    ps = pattern_seq(mod_ctx.sigma, cls, p)
    if isinstance(k, Constr) and subtype(mod_ctx.sigma, ClassType(k.c), ClassType(cls)):
        seqs = match_seq(k.args, padded(ps, len(k.args)), p, mod_ctx)
        return map_seq_match(lambda r: Constr(k.c, r, k.heads), seqs)
    return None


def split(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Split | None:
    sigma = mod_ctx.sigma
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return split_literal(sigma, k, literal_of(p))
    if isinstance(p, PatTuple):
        return split_tuple(sigma, k, len(p.patterns))
    if isinstance(p, PatList):
        return split_list(sigma, k, len(p.patterns))
    if isinstance(p, ast.MatchMapping):
        return split_dict(sigma, k, key_patterns(p))
    assert isinstance(p, ast.MatchClass)
    cls = class_of_pattern(p, mod_ctx)
    if isinstance(k, Rest):
        return split_class(sigma, k, cls)
    if isinstance(k, Constr):
        return split_subclass(sigma, k, cls)
    return None


def split_literal(sigma: ClassTable, k: Shape, ell: LiteralType) -> Split | None:
    if (
        isinstance(k, Rest)
        and ell not in k.heads
        and subtype(sigma, ell, k.ty)
        and not isinstance(k.ty, LiteralType)
    ):
        return (Rest(ell, frozenset()),), shapes(sigma, k.ty, k.heads | {ell})
    return None


def split_tuple(sigma: ClassTable, k: Shape, n: int) -> Split | None:
    if not (isinstance(k, Rest) and isinstance(k.ty, TupleType)):
        return None
    if len(k.ty.components) != n:
        return None
    assert not k.heads
    return tuple(Tuple(ks) for ks in shapes_seq(sigma, k.ty.components)), ()


def split_list(sigma: ClassTable, k: Shape, n: int) -> Split | None:
    if not (isinstance(k, Rest) and isinstance(k.ty, ListType) and n not in k.heads):
        return None
    elem = k.ty.elem
    return (
        tuple(List(elem, ks) for ks in shapes_seq(sigma, (elem,) * n)),
        shapes(sigma, k.ty, k.heads | {n}),
    )


def split_dict(
    sigma: ClassTable, k: Shape, ws: tuple[tuple[str, ast.pattern], ...]
) -> Split | None:
    if not isinstance(k, Dict):
        return None
    bound = dict(k.bound)
    w = next((w for w, _ in ws if w not in bound), None)
    if w is None or w in k.heads:
        return None
    return (
        tuple(with_keys(k, (w,), (m,)) for m in shapes(sigma, k.value, frozenset())),
        (Dict(k.value, k.bound, k.heads | {w}),),
    )


def split_class(sigma: ClassTable, k: Rest, cls: Class) -> Split | None:
    if below_excluded(sigma, cls, k.heads):
        return None
    low = meet(sigma, k.ty, ClassType(cls))
    if not isinstance(low, ClassType):
        return None
    types = tuple(declared_type(sigma, low.c, x) for x in fields(sigma, low.c))
    kept = typed_heads(sigma, k.heads, low)
    return (
        tuple(Constr(low.c, ks, kept) for ks in shapes_seq(sigma, types)),
        shapes(sigma, k.ty, k.heads | {cls}),
    )


def split_subclass(sigma: ClassTable, k: Constr, cls: Class) -> Split | None:
    if cls == k.c or not subtype(sigma, ClassType(cls), ClassType(k.c)):
        return None
    if below_excluded(sigma, cls, k.heads):
        return None
    own = tuple(declared_type(sigma, cls, x) for x in fields(sigma, cls)[len(k.args) :])
    kept = typed_heads(sigma, k.heads, ClassType(cls))
    return (
        tuple(Constr(cls, k.args + ks, kept) for ks in shapes_seq(sigma, own)),
        (Constr(k.c, k.args, k.heads | {cls}),),
    )


def class_of_pattern(p: ast.MatchClass, mod_ctx: ModuleContext) -> Class:
    cls = class_of_name(p.cls, mod_ctx)
    if cls is None:
        raise IllFormedModule(p, reasons.UnknownClassInPattern(qualified_name(p.cls)))
    return cls


def pattern_seq(
    sigma: ClassTable, cls: Class, p: ast.MatchClass
) -> tuple[ast.pattern, ...]:
    args = field_map(sigma, cls, p.patterns, p.kwd_attrs, p.kwd_patterns)
    if args is None:
        raise no_field_map(sigma, cls, p)
    return tuple(args[x] for x in fields(sigma, cls))


def match_seq(
    ks: Seq, ps: tuple[ast.pattern, ...], node: ast.pattern, mod_ctx: ModuleContext
) -> SeqMatch | None:
    matches = [match(k, p, mod_ctx) for k, p in zip(ks, ps)]
    if any(s is None for s in matches):
        return None
    parts = [s for s in matches if s is not None]
    matched = tuple(product(*(m for m, _, _ in parts)))
    residual = tuple(
        tuple(prefix) + (k,) + ks[i + 1 :]
        for i, (_, ls, _) in enumerate(parts)
        for prefix in product(*(parts[j][0] for j in range(i)))
        for k in ls
    )
    return matched, residual, pattern_bindings([d for _, _, d in parts], node)


def match_shapes(
    ks: tuple[Shape, ...], p: ast.pattern, mod_ctx: ModuleContext
) -> Match | None:
    results = {k: match(k, p, mod_ctx) for k in ks}
    matches = {k: m for k, m in results.items() if m is not None}
    if len(matches) == 0:
        return None
    matched = union(m for m, _, _ in matches.values())
    unmatched = tuple(k for k in ks if k not in matches)
    residual = union(residual for _, residual, _ in matches.values()) + unmatched
    return (
        matched,
        residual,
        join_context(mod_ctx.sigma, [d for _, _, d in matches.values()]),
    )


def seq_safe(p: ast.pattern, t: Type, mod_ctx: ModuleContext) -> bool:
    if isinstance(t, UnionType):
        return seq_safe(p, t.left, mod_ctx) and seq_safe(p, t.right, mod_ctx)
    if isinstance(p, PatTuple):
        if isinstance(t, ListType) or t in (Primitive.SIZED, Primitive.OBJECT):
            return False
        if isinstance(t, TupleType) and len(t.components) == len(p.patterns):
            return all(
                seq_safe(q, c, mod_ctx) for q, c in zip(p.patterns, t.components)
            )
        return True
    if isinstance(p, PatList):
        if isinstance(t, TupleType) or t in (Primitive.SIZED, Primitive.OBJECT):
            return False
        if isinstance(t, ListType):
            return all(seq_safe(q, t.elem, mod_ctx) for q in p.patterns)
        return True
    if isinstance(p, ast.MatchMapping):
        if isinstance(t, DictType):
            return all(seq_safe(q, t.value, mod_ctx) for q in p.patterns)
        return True
    if isinstance(p, ast.MatchClass):
        cls = class_of_name(p.cls, mod_ctx)
        if cls is None:
            return True  # the match rules reject with a sharper reason
        args = field_map(mod_ctx.sigma, cls, p.patterns, p.kwd_attrs, p.kwd_patterns)
        if args is None:
            return True  # likewise
        return all(
            seq_safe(args[x], declared_type(mod_ctx.sigma, cls, x), mod_ctx)
            for x in fields(mod_ctx.sigma, cls)
        )
    if isinstance(p, ast.MatchAs):
        return p.pattern is None or seq_safe(p.pattern, t, mod_ctx)
    return True


def pattern_bindings(deltas: list[VarContext], node: ast.AST) -> VarContext:
    merged: VarContext = {}
    for delta in deltas:
        repeated = sorted(merged.keys() & delta.keys())
        if len(repeated) > 0:
            raise IllFormedModule(node, reasons.NonlinearPattern(repeated[0]))
        merged = disjoint_union(merged, delta)
    return merged


def union(seqs: Iterable[tuple[Shape, ...]]) -> tuple[Shape, ...]:
    return tuple(k for s in seqs for k in s)


def map_seq_match(form: Callable[[Seq], Shape], seqs: SeqMatch | None) -> Match | None:
    if seqs is None:
        return None
    matched, residual, delta = seqs
    return (
        tuple(form(ks) for ks in matched),
        tuple(form(ks) for ks in residual),
        delta,
    )


def padded(ps: tuple[ast.pattern, ...], n: int) -> tuple[ast.pattern, ...]:
    return ps + tuple(ast.MatchAs() for _ in range(n - len(ps)))


def no_field_map(sigma: ClassTable, cls: Class, p: ast.MatchClass) -> IllFormedModule:
    """Why field-map is undefined for the pattern's arguments."""
    c, xs = short_name(cls), fields(sigma, cls)
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
    bound = dict(k.bound) | dict(zip(ws, ks))
    return Dict(k.value, tuple(sorted(bound.items())), k.heads)


def key_patterns(p: ast.MatchMapping) -> tuple[tuple[str, ast.pattern], ...]:
    return tuple(zip([string_literal(key) for key in p.keys], p.patterns))


def string_literal(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)
    return k.value


def literal_of(p: ast.pattern) -> LiteralType:
    if isinstance(p, ast.MatchSingleton):
        return LiteralType(p.value)
    assert isinstance(p, ast.MatchValue)
    t = literal_type(p.value)
    assert t is not None
    return t
