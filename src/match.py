import ast
from collections.abc import Callable, Iterable
from itertools import product

import reasons
from aux import name_of
from classes import (
    ArityMismatch,
    Class,
    ClassTable,
    RepeatedKeywordArg,
    UnknownKeywordArgs,
    ancestors,
    field_map,
    field_names,
    fields,
    no_field_map,
    short_name,
)
from contexts import (
    ModuleContext,
    Unbound,
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
    Shape,
    Shapes,
    ShapeSeq,
    ShapeSeqs,
    Tuple,
    below_excluded,
    shape_type,
    shapes,
    shapes_seq,
    typed_heads,
)
from subtyping import Undetermined, instance, join, join_seq, meet, members, subtype
from syntax import PatList, PatTuple
from type_syntax import (
    ClassType,
    DictType,
    ListType,
    Literal,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
    instantiate,
    literal,
)

type Match = tuple[Shapes, Shapes, VarContext]
type SeqMatch = tuple[ShapeSeqs, ShapeSeqs, VarContext]
type Split = tuple[Shapes, Shapes]


def match(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
    match p:
        case ast.MatchAs():
            return match_as(k, p, mod_ctx)
        case ast.MatchValue() | ast.MatchSingleton():
            result = match_literal(k, literal_of(p))
        case PatTuple():
            result = match_tuple(k, p, mod_ctx)
        case PatList():
            result = match_list(k, p, mod_ctx)
        case ast.MatchMapping():
            result = match_dict(k, p, mod_ctx)
        case ast.MatchClass():
            result = match_constr(k, p, mod_ctx)
        case _:
            assert False
    return result if result is not None else match_split(k, p, mod_ctx)


def match_as(k: Shape, p: ast.MatchAs, mod_ctx: ModuleContext) -> Match | None:
    if p.name is not None and mod_ctx.gamma.get(p.name) != Unbound():
        raise IllFormedModule(p, reasons.Redeclaration(p.name))
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


def match_literal(k: Shape, ell: Literal) -> Match | None:
    match k:
        case Rest(tau, hs):
            if tau == LiteralType(ell):
                assert len(hs) == 0
                return (k,), (), {}
            return None
        case _:
            return None


def match_tuple(k: Shape, p: PatTuple, mod_ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    match k:
        case Tuple(ks):
            if len(ks) == len(ps):
                return map_seq_match(Tuple, match_seq(ks, ps, p, mod_ctx))
            return None
        case _:
            return None


def match_list(k: Shape, p: PatList, mod_ctx: ModuleContext) -> Match | None:
    ps = tuple(p.patterns)
    match k:
        case List(tau, ks):
            if len(ks) == len(ps):
                return map_seq_match(lambda ks_: List(tau, ks_), match_seq(ks, ps, p, mod_ctx))
            return None
        case _:
            return None


def match_dict(k: Shape, p: ast.MatchMapping, mod_ctx: ModuleContext) -> Match | None:
    match k:
        case Dict():
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
        case _:
            return None


def match_constr(k: Shape, p: ast.MatchClass, mod_ctx: ModuleContext) -> Match | None:
    c = class_of_pattern(p, mod_ctx)
    ps = pattern_seq(mod_ctx.Sigma, c, p)
    match k:
        case Constr(tau, ks, hs):
            if c in ancestors(mod_ctx.Sigma, tau.c):
                result = match_seq(ks, padded(ps, len(ks)), p, mod_ctx)
                return map_seq_match(lambda ks_: Constr(tau, ks_, hs), result)
            return None
        case _:
            return None


def split(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Split | None:
    Sigma = mod_ctx.Sigma
    match p:
        case ast.MatchValue() | ast.MatchSingleton():
            return split_literal(Sigma, k, literal_of(p))
        case PatTuple(patterns=ps):
            return split_tuple(Sigma, k, len(ps))
        case PatList(patterns=ps):
            return split_list(Sigma, k, len(ps))
        case ast.MatchMapping():
            return split_dict(Sigma, k, key_patterns(p))
        case ast.MatchClass():
            c = class_of_pattern(p, mod_ctx)
            match k:
                case Rest():
                    return split_class(Sigma, k, c, p)
                case Constr():
                    return split_subclass(Sigma, k, c, p)
                case _:
                    return None
        case _:
            assert False


def split_literal(Sigma: ClassTable, k: Shape, ell: Literal) -> Split | None:
    match k:
        case Rest(tau, hs):
            if (
                ell not in hs
                and subtype(Sigma, LiteralType(ell), tau)
                and not isinstance(tau, LiteralType)
            ):
                return (Rest(LiteralType(ell), frozenset()),), shapes(Sigma, tau, hs | {ell})
            return None
        case _:
            return None


def split_tuple(Sigma: ClassTable, k: Shape, n: int) -> Split | None:
    match k:
        case Rest(TupleType(taus), hs):
            if len(taus) != n:
                return None
            assert len(hs) == 0
            return tuple(Tuple(ks) for ks in shapes_seq(Sigma, taus)), ()
        case _:
            return None


def split_list(Sigma: ClassTable, k: Shape, n: int) -> Split | None:
    match k:
        case Rest(ListType(tau), hs):
            if n in hs:
                return None
            return (
                tuple(List(tau, ks) for ks in shapes_seq(Sigma, (tau,) * n)),
                shapes(Sigma, k.ty, hs | {n}),
            )
        case _:
            return None


def split_dict(
    Sigma: ClassTable, k: Shape, ws: tuple[tuple[str, ast.pattern], ...]
) -> Split | None:
    match k:
        case Dict():
            beta = dict(k.beta)
            w = next((w for w, _ in ws if w not in beta), None)
            if w is None or w in k.hs:
                return None
            return (
                tuple(with_keys(k, (w,), (m,)) for m in shapes(Sigma, k.value, frozenset())),
                (Dict(k.value, k.beta, k.hs | {w}),),
            )
        case _:
            return None


def split_class(Sigma: ClassTable, k: Rest, c: Class, p: ast.MatchClass) -> Split | None:
    if below_excluded(Sigma, c, k.hs):
        return None
    sigma = pattern_instance(Sigma, c, k.ty)
    if sigma is None:
        return None
    tau = meet(Sigma, k.ty, sigma)
    assert isinstance(tau, ClassType)
    sigmas = tuple(sigma_ for _, sigma_ in instantiate(fields(Sigma, tau.c), tau.args))
    hs_ = typed_heads(Sigma, k.hs, tau)
    return (
        tuple(Constr(tau, ks, hs_) for ks in shapes_seq(Sigma, sigmas)),
        shapes(Sigma, k.ty, k.hs | {c}),
    )


def split_subclass(Sigma: ClassTable, k: Constr, c: Class, p: ast.MatchClass) -> Split | None:
    sigma = pattern_instance(Sigma, c, k.ty)
    if sigma is None or c == k.ty.c or not subtype(Sigma, sigma, k.ty):
        return None
    if below_excluded(Sigma, c, k.hs):
        return None
    sigmas = tuple(sigma_ for _, sigma_ in instantiate(fields(Sigma, c), sigma.args)[len(k.args) :])
    hs_ = typed_heads(Sigma, k.hs, sigma)
    return (
        tuple(Constr(sigma, k.args + ks, hs_) for ks in shapes_seq(Sigma, sigmas)),
        (Constr(k.ty, k.args, k.hs | {c}),),
    )


def pattern_instance(Sigma: ClassTable, c: Class, tau: Type) -> ClassType | None:
    sigma = instance(Sigma, c, tau)
    assert not isinstance(sigma, Undetermined)  # pattern checks against the scrutinee type
    return sigma


def class_of_pattern(p: ast.MatchClass, mod_ctx: ModuleContext) -> Class:
    c = class_of_name(p.cls, mod_ctx)
    if c is None:
        raise IllFormedModule(p, reasons.NotClass(name_of(p.cls)))
    return c


def pattern_seq(Sigma: ClassTable, c: Class, p: ast.MatchClass) -> tuple[ast.pattern, ...]:
    args = field_map(Sigma, c, p.patterns, p.kwd_attrs, p.kwd_patterns)
    if args is None:
        name = short_name(c)
        match no_field_map(Sigma, c, len(p.patterns), p.kwd_attrs):
            case ArityMismatch(expected, given):
                raise IllFormedModule(p, reasons.PatternArityMismatch(name, expected, given))
            case RepeatedKeywordArg():
                raise IllFormedModule(p, reasons.DuplicatePatternKeyword(name))
            case UnknownKeywordArgs(xs):
                raise IllFormedModule(p, reasons.UnknownFieldInPattern(name, xs))
    return tuple(args[x] for x in field_names(Sigma, c))


def match_seq(
    ks: ShapeSeq, ps: tuple[ast.pattern, ...], node: ast.pattern, mod_ctx: ModuleContext
) -> SeqMatch | None:
    results = [match(k, p, mod_ctx) for k, p in zip(ks, ps)]
    if any(result is None for result in results):
        return None
    matches = [result for result in results if result is not None]
    matched_sets = [matched for matched, _, _ in matches]
    residual_sets = [residual for _, residual, _ in matches]
    deltas = [delta for _, _, delta in matches]
    matched = tuple(product(*matched_sets))
    residual = tuple(
        prefix + (k,) + ks[i + 1 :]
        for i, ls in enumerate(residual_sets)
        for prefix in product(*matched_sets[:i])
        for k in ls
    )
    return matched, residual, pattern_bindings(deltas, node)


def match_shapes(residual: Shapes, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
    results = {k: match(k, p, mod_ctx) for k in residual}
    matches = {k: result for k, result in results.items() if result is not None}
    if len(matches) == 0:
        return None
    matched = union(matched_k for matched_k, _, _ in matches.values())
    unmatched = tuple(k for k in residual if k not in matches)
    residual_ = union(residual_k for _, residual_k, _ in matches.values()) + unmatched
    return (
        matched,
        residual_,
        join_context(mod_ctx.Sigma, [d for _, _, d in matches.values()]),
    )


def check_pattern(p: ast.pattern, tau: Type, mod_ctx: ModuleContext) -> None:
    Sigma = mod_ctx.Sigma
    match p:
        case PatTuple(patterns=ps):
            if has_list_values(Sigma, tau):
                raise IllFormedModule(p, reasons.SequenceKindMismatch("tuple", tau))
            for sigma in members(tau):
                if isinstance(sigma, TupleType) and len(sigma.components) == len(ps):
                    for q, sigma_ in zip(ps, sigma.components):
                        check_pattern(q, sigma_, mod_ctx)
        case PatList(patterns=ps):
            if has_tuple_values(Sigma, tau):
                raise IllFormedModule(p, reasons.SequenceKindMismatch("list", tau))
            for sigma in members(tau):
                if isinstance(sigma, ListType):
                    for q in ps:
                        check_pattern(q, sigma.elem, mod_ctx)
        case ast.MatchMapping(patterns=ps):
            for sigma in members(tau):
                if isinstance(sigma, DictType):
                    for q in ps:
                        check_pattern(q, sigma.value, mod_ctx)
        case ast.MatchClass():
            c = class_of_pattern(p, mod_ctx)
            # Checked before the instance; the rules would report a pattern with no instance as unreachable
            qs = pattern_seq(Sigma, c, p)
            for sigma in members(tau):
                match instance(Sigma, c, sigma):
                    case Undetermined():
                        raise IllFormedModule(
                            p, reasons.PatternClassUndetermined(short_name(c), sigma)
                        )
                    case None:
                        pass
                    case cls:
                        sigmas = [sigma_ for _, sigma_ in instantiate(fields(Sigma, c), cls.args)]
                        for q, sigma_ in zip(qs, sigmas):
                            check_pattern(q, sigma_, mod_ctx)
        case ast.MatchAs(pattern=q) if q is not None:
            check_pattern(q, tau, mod_ctx)
        case _:
            pass


def remaining_seq(tau: Type, ps: list[ast.pattern], mod_ctx: ModuleContext) -> Type:
    match ps:
        case [p, *ps_]:
            return remaining_seq(remaining(tau, p, mod_ctx), ps_, mod_ctx)
        case _:
            return tau


def remaining(tau: Type, p: ast.pattern, mod_ctx: ModuleContext) -> Type:
    Sigma = mod_ctx.Sigma
    match tau, p:
        case UnionType(sigma, sigma_), _:
            return join(Sigma, remaining(sigma, p, mod_ctx), remaining(sigma_, p, mod_ctx))
        case _, ast.MatchAs(pattern=None):
            return Primitive.NEVER
        case _, ast.MatchAs(pattern=ast.pattern() as q):
            return remaining(tau, q, mod_ctx)
        case _, ast.MatchValue() | ast.MatchSingleton():
            ell = literal_of(p)
            if tau == LiteralType(ell) or (tau == Primitive.NONE and ell == Literal(None)):
                return Primitive.NEVER
            if tau == Primitive.BOOL and isinstance(ell.value, bool):
                return LiteralType(Literal(not ell.value))
            return tau
        case TupleType(taus), PatTuple(patterns=ps) if len(taus) == len(ps):
            rests = [remaining(sigma, q, mod_ctx) for sigma, q in zip(taus, ps)]
            match [i for i, rest in enumerate(rests) if rest != Primitive.NEVER]:
                case []:
                    return Primitive.NEVER
                case [i]:
                    return TupleType(
                        tuple(rests[i] if j == i else tau_ for j, tau_ in enumerate(taus))
                    )
                case _:
                    return tau
        case DictType(), ast.MatchMapping(keys=[]):
            return Primitive.NEVER
        case _, ast.MatchClass():
            c = class_of_pattern(p, mod_ctx)
            cls = pattern_instance(Sigma, c, tau)
            if cls is None or not subtype(Sigma, tau, cls):
                return tau
            qs = pattern_seq(Sigma, c, p)
            sigmas = [sigma_ for _, sigma_ in instantiate(fields(Sigma, c), cls.args)]
            if all(
                remaining(sigma_, q, mod_ctx) == Primitive.NEVER for q, sigma_ in zip(qs, sigmas)
            ):
                return Primitive.NEVER
            return tau
        case _:
            return tau


def has_list_values(Sigma: ClassTable, tau: Type) -> bool:
    # A member other than a list type is above every list type or none, so list[object] stands for all
    return any(
        isinstance(sigma, ListType) or subtype(Sigma, ListType(Primitive.OBJECT), sigma)
        for sigma in members(tau)
    )


def has_tuple_values(Sigma: ClassTable, tau: Type) -> bool:
    # A member other than a tuple type is above every tuple type or none, so tuple[()] stands for all
    return any(
        isinstance(sigma, TupleType) or subtype(Sigma, TupleType(()), sigma)
        for sigma in members(tau)
    )


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


def map_seq_match(form: Callable[[ShapeSeq], Shape], result: SeqMatch | None) -> Match | None:
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


def with_keys(k: Dict, ws: tuple[str, ...], ks: ShapeSeq) -> Dict:
    beta = dict(k.beta) | dict(zip(ws, ks))
    return Dict(k.value, tuple(sorted(beta.items())), k.hs)


def key_patterns(p: ast.MatchMapping) -> tuple[tuple[str, ast.pattern], ...]:
    return tuple(zip([string_literal(key) for key in p.keys], p.patterns))


def string_literal(k: ast.expr) -> str:
    assert isinstance(k, ast.Constant) and isinstance(k.value, str)
    return k.value


def literal_of(p: ast.pattern) -> Literal:
    match p:
        case ast.MatchSingleton():
            return Literal(p.value)
        case ast.MatchValue(value=e):
            ell = literal(e)
            assert ell is not None
            return ell
        case _:
            assert False
