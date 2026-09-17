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
    Shapes,
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

type Match = tuple[Shapes, Shapes, VarContext]
type SeqMatch = tuple[tuple[Seq, ...], tuple[Seq, ...], VarContext]
type Split = tuple[Shapes, Shapes]


def match(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
    if isinstance(p, ast.MatchAs):
        return match_as(k, p, mod_ctx)
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        result = match_literal(k, literal_of(p))
    elif isinstance(p, PatTuple):
        result = match_tuple(k, p, mod_ctx)
    elif isinstance(p, PatList):
        result = match_list(k, p, mod_ctx)
    elif isinstance(p, ast.MatchMapping):
        result = match_dict(k, p, mod_ctx)
    else:
        assert isinstance(p, ast.MatchClass)
        result = match_constr(k, p, mod_ctx)
    return result if result is not None else match_split(k, p, mod_ctx)


def match_as(k: Shape, p: ast.MatchAs, mod_ctx: ModuleContext) -> Match | None:
    if p.pattern is None:
        delta: VarContext = {} if p.name is None else {p.name: shape_type(k)}
        return (k,), (), delta
    result = match(k, p.pattern, mod_ctx)
    if result is None:
        return None
    matched, residual, delta = result
    if p.name is None:
        return matched, residual, delta
    tau = join_seq(mod_ctx.Sigma, [shape_type(k_) for k_ in matched])
    return matched, residual, pattern_bindings([delta, {p.name: tau}], p)


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
            lambda ks: List(k.elem, ks), match_seq(k.elems, ps, p, mod_ctx)
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
    beta = dict(k.beta)
    if any(w not in beta for w in keys):
        return None
    ks = tuple(beta[w] for w in keys)
    result = match_seq(ks, tuple(q for _, q in ws), p, mod_ctx)
    return map_seq_match(lambda ks_: with_keys(k, keys, ks_), result)


def match_constr(k: Shape, p: ast.MatchClass, mod_ctx: ModuleContext) -> Match | None:
    c = class_of_pattern(p, mod_ctx)
    ps = pattern_seq(mod_ctx.Sigma, c, p)
    if isinstance(k, Constr) and subtype(mod_ctx.Sigma, ClassType(k.c), ClassType(c)):
        result = match_seq(k.args, padded(ps, len(k.args)), p, mod_ctx)
        return map_seq_match(lambda ks: Constr(k.c, ks, k.heads), result)
    return None


def split(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Split | None:
    Sigma = mod_ctx.Sigma
    if isinstance(p, (ast.MatchValue, ast.MatchSingleton)):
        return split_literal(Sigma, k, literal_of(p))
    if isinstance(p, PatTuple):
        return split_tuple(Sigma, k, len(p.patterns))
    if isinstance(p, PatList):
        return split_list(Sigma, k, len(p.patterns))
    if isinstance(p, ast.MatchMapping):
        return split_dict(Sigma, k, key_patterns(p))
    assert isinstance(p, ast.MatchClass)
    c = class_of_pattern(p, mod_ctx)
    if isinstance(k, Rest):
        return split_class(Sigma, k, c)
    if isinstance(k, Constr):
        return split_subclass(Sigma, k, c)
    return None


def split_literal(Sigma: ClassTable, k: Shape, ell: LiteralType) -> Split | None:
    if (
        isinstance(k, Rest)
        and ell not in k.heads
        and subtype(Sigma, ell, k.ty)
        and not isinstance(k.ty, LiteralType)
    ):
        return (Rest(ell, frozenset()),), shapes(Sigma, k.ty, k.heads | {ell})
    return None


def split_tuple(Sigma: ClassTable, k: Shape, n: int) -> Split | None:
    if not (isinstance(k, Rest) and isinstance(k.ty, TupleType)):
        return None
    if len(k.ty.components) != n:
        return None
    assert not k.heads
    return tuple(Tuple(ks) for ks in shapes_seq(Sigma, k.ty.components)), ()


def split_list(Sigma: ClassTable, k: Shape, n: int) -> Split | None:
    if not (isinstance(k, Rest) and isinstance(k.ty, ListType) and n not in k.heads):
        return None
    elem = k.ty.elem
    return (
        tuple(List(elem, ks) for ks in shapes_seq(Sigma, (elem,) * n)),
        shapes(Sigma, k.ty, k.heads | {n}),
    )


def split_dict(
    Sigma: ClassTable, k: Shape, ws: tuple[tuple[str, ast.pattern], ...]
) -> Split | None:
    if not isinstance(k, Dict):
        return None
    beta = dict(k.beta)
    w = next((w for w, _ in ws if w not in beta), None)
    if w is None or w in k.heads:
        return None
    return (
        tuple(with_keys(k, (w,), (m,)) for m in shapes(Sigma, k.value, frozenset())),
        (Dict(k.value, k.beta, k.heads | {w}),),
    )


def split_class(Sigma: ClassTable, k: Rest, c: Class) -> Split | None:
    if below_excluded(Sigma, c, k.heads):
        return None
    tau = meet(Sigma, k.ty, ClassType(c))
    if not isinstance(tau, ClassType):
        return None
    d = tau.c
    sigmas = tuple(declared_type(Sigma, d, x) for x in fields(Sigma, d))
    heads_ = typed_heads(Sigma, k.heads, tau)
    return (
        tuple(Constr(d, ks, heads_) for ks in shapes_seq(Sigma, sigmas)),
        shapes(Sigma, k.ty, k.heads | {c}),
    )


def split_subclass(Sigma: ClassTable, k: Constr, c: Class) -> Split | None:
    if c == k.c or not subtype(Sigma, ClassType(c), ClassType(k.c)):
        return None
    if below_excluded(Sigma, c, k.heads):
        return None
    sigmas = tuple(declared_type(Sigma, c, x) for x in fields(Sigma, c)[len(k.args) :])
    heads_ = typed_heads(Sigma, k.heads, ClassType(c))
    return (
        tuple(Constr(c, k.args + ks, heads_) for ks in shapes_seq(Sigma, sigmas)),
        (Constr(k.c, k.args, k.heads | {c}),),
    )


def class_of_pattern(p: ast.MatchClass, mod_ctx: ModuleContext) -> Class:
    c = class_of_name(p.cls, mod_ctx)
    if c is None:
        raise IllFormedModule(p, reasons.NotClass(qualified_name(p.cls)))
    return c


def pattern_seq(
    Sigma: ClassTable, c: Class, p: ast.MatchClass
) -> tuple[ast.pattern, ...]:
    args = field_map(Sigma, c, p.patterns, p.kwd_attrs, p.kwd_patterns)
    if args is None:
        raise no_field_map(Sigma, c, p)
    return tuple(args[x] for x in fields(Sigma, c))


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


def match_shapes(ks: Shapes, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
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
        join_context(mod_ctx.Sigma, [d for _, _, d in matches.values()]),
    )


def seq_safe(p: ast.pattern, tau: Type, mod_ctx: ModuleContext) -> bool:
    if isinstance(tau, UnionType):
        return seq_safe(p, tau.left, mod_ctx) and seq_safe(p, tau.right, mod_ctx)
    if isinstance(p, PatTuple):
        if isinstance(tau, ListType) or tau in (Primitive.SIZED, Primitive.OBJECT):
            return False
        if isinstance(tau, TupleType) and len(tau.components) == len(p.patterns):
            return all(
                seq_safe(q, c, mod_ctx) for q, c in zip(p.patterns, tau.components)
            )
        return True
    if isinstance(p, PatList):
        if isinstance(tau, TupleType) or tau in (Primitive.SIZED, Primitive.OBJECT):
            return False
        if isinstance(tau, ListType):
            return all(seq_safe(q, tau.elem, mod_ctx) for q in p.patterns)
        return True
    if isinstance(p, ast.MatchMapping):
        if isinstance(tau, DictType):
            return all(seq_safe(q, tau.value, mod_ctx) for q in p.patterns)
        return True
    if isinstance(p, ast.MatchClass):
        c = class_of_name(p.cls, mod_ctx)
        if c is None:
            return True  # the match rules reject with a sharper reason
        args = field_map(mod_ctx.Sigma, c, p.patterns, p.kwd_attrs, p.kwd_patterns)
        if args is None:
            return True  # likewise
        return all(
            seq_safe(args[x], declared_type(mod_ctx.Sigma, c, x), mod_ctx)
            for x in fields(mod_ctx.Sigma, c)
        )
    if isinstance(p, ast.MatchAs):
        return p.pattern is None or seq_safe(p.pattern, tau, mod_ctx)
    return True


def pattern_bindings(deltas: list[VarContext], node: ast.AST) -> VarContext:
    merged: VarContext = {}
    for delta in deltas:
        repeated = sorted(merged.keys() & delta.keys())
        if len(repeated) > 0:
            raise IllFormedModule(node, reasons.NonlinearPattern(repeated[0]))
        merged = disjoint_union(merged, delta)
    return merged


def union(kss: Iterable[Shapes]) -> Shapes:
    return tuple(k for ks in kss for k in ks)


def map_seq_match(
    form: Callable[[Seq], Shape], result: SeqMatch | None
) -> Match | None:
    if result is None:
        return None
    matched, residual, delta = result
    return (
        tuple(form(ks) for ks in matched),
        tuple(form(ks) for ks in residual),
        delta,
    )


def padded(ps: tuple[ast.pattern, ...], n: int) -> tuple[ast.pattern, ...]:
    return ps + tuple(ast.MatchAs() for _ in range(n - len(ps)))


def no_field_map(Sigma: ClassTable, c: Class, p: ast.MatchClass) -> IllFormedModule:
    """Why field-map is undefined for a pattern's arguments."""
    name, xs = short_name(c), fields(Sigma, c)
    n = len(p.patterns)
    if n + len(p.kwd_attrs) != len(xs):
        return IllFormedModule(
            p, reasons.PatternArityMismatch(name, len(xs), n + len(p.kwd_attrs))
        )
    if len(p.kwd_attrs) != len(set(p.kwd_attrs)):
        return IllFormedModule(p, reasons.DuplicatePatternKeyword(name))
    return IllFormedModule(
        p, reasons.UnknownFieldInPattern(name, tuple(sorted(set(xs[n:]))))
    )


def with_keys(k: Dict, ws: tuple[str, ...], ks: Seq) -> Dict:
    beta = dict(k.beta) | dict(zip(ws, ks))
    return Dict(k.value, tuple(sorted(beta.items())), k.heads)


def key_patterns(p: ast.MatchMapping) -> tuple[tuple[str, ast.pattern], ...]:
    return tuple(zip([string_literal(key) for key in p.keys], p.patterns))


def string_literal(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)
    return k.value


def literal_of(p: ast.pattern) -> LiteralType:
    if isinstance(p, ast.MatchSingleton):
        return LiteralType(p.value)
    assert isinstance(p, ast.MatchValue)
    tau = literal_type(p.value)
    assert tau is not None
    return tau
