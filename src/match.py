import ast
from collections.abc import Callable, Iterable, Sequence
from itertools import product

import reasons
from aux import binds, name_of
from classes import (
    ArityMismatch,
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
    DU,
    PU,
    ModuleContext,
    Unbound,
    VarContext,
    VarEntry,
    class_of_name,
    disjoint_union,
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
    shapes,
    shapes_seq,
    typed_heads,
)
from subtyping import Undetermined, disjuncts, instance, join, join_seq, meet, subtype
from syntax import PatList, PatTuple
from type_syntax import (
    RANGE,
    Class,
    ClassType,
    DictType,
    ListType,
    Literal,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
    Var,
    instantiate,
    literal,
)

type Match = tuple[Shapes, Shapes]
type SeqMatch = tuple[ShapeSeqs, ShapeSeqs]
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
    if p.pattern is None:
        return (k,), ()
    return match(k, p.pattern, mod_ctx)


def match_split(k: Shape, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
    parts = split(k, p, mod_ctx)
    if parts is None:
        return None
    ks, residual = parts
    result = match_shapes(ks, p, mod_ctx)
    if result is None:
        return None
    matched, residual_ = result
    return matched, residual + residual_


def match_literal(k: Shape, ell: Literal) -> Match | None:
    match k:
        case Rest(tau, hs):
            if tau == LiteralType(ell):
                assert len(hs) == 0
                return (k,), ()
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
    if c == RANGE:
        raise IllFormedModule(p, reasons.RangePattern())
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
    matched_sets = [matched for matched, _ in matches]
    residual_sets = [residual for _, residual in matches]
    matched = tuple(product(*matched_sets))
    residual = tuple(
        prefix + (k,) + ks[i + 1 :]
        for i, ls in enumerate(residual_sets)
        for prefix in product(*matched_sets[:i])
        for k in ls
    )
    return matched, residual


def match_shapes(residual: Shapes, p: ast.pattern, mod_ctx: ModuleContext) -> Match | None:
    results = {k: match(k, p, mod_ctx) for k in residual}
    matches = {k: result for k, result in results.items() if result is not None}
    if len(matches) == 0:
        return None
    matched = union(matched_k for matched_k, _ in matches.values())
    unmatched = tuple(k for k in residual if k not in matches)
    residual_ = union(residual_k for _, residual_k in matches.values()) + unmatched
    return matched, residual_


def check_pattern(p: ast.pattern, tau: Type, mod_ctx: ModuleContext) -> VarContext:
    Sigma = mod_ctx.Sigma
    match p:
        case ast.MatchAs(pattern=None, name=None):
            return {}
        case ast.MatchAs(pattern=None, name=str() as x):
            check_unbound(x, p, mod_ctx)
            return {x: tau}
        case ast.MatchAs(pattern=ast.pattern() as q, name=str() as x):
            check_unbound(x, p, mod_ctx)
            delta = check_pattern(q, tau, mod_ctx)
            return pattern_bindings([delta, {x: matched_as(tau, q, mod_ctx)}], p)
        case ast.MatchValue() | ast.MatchSingleton():
            return {}
        case PatTuple(patterns=ps):
            if has_list_values(Sigma, tau):
                raise IllFormedModule(p, reasons.SequenceKindMismatch("tuple", tau))
            return bindings_at(
                tau,
                p,
                mod_ctx,
                lambda sigma: (
                    check_seq(ps, sigma.components, p, mod_ctx)
                    if isinstance(sigma, TupleType) and len(sigma.components) == len(ps)
                    else None
                ),
            )
        case PatList(patterns=ps):
            if has_tuple_values(Sigma, tau):
                raise IllFormedModule(p, reasons.SequenceKindMismatch("list", tau))
            return bindings_at(
                tau,
                p,
                mod_ctx,
                lambda sigma: (
                    check_seq(ps, [sigma.elem] * len(ps), p, mod_ctx)
                    if isinstance(sigma, ListType)
                    else None
                ),
            )
        case ast.MatchMapping(patterns=ps):
            return bindings_at(
                tau,
                p,
                mod_ctx,
                lambda sigma: (
                    check_seq(ps, [sigma.value] * len(ps), p, mod_ctx)
                    if isinstance(sigma, DictType)
                    else None
                ),
            )
        case ast.MatchClass():
            c = class_of_pattern(p, mod_ctx)
            # Checked before the instance; the rules would report a pattern with no instance as unreachable
            qs = pattern_seq(Sigma, c, p)

            def at_disjunct(sigma: Type) -> VarContext | None:
                match instance(Sigma, c, sigma):
                    case Undetermined():
                        raise IllFormedModule(
                            p, reasons.PatternClassUndetermined(short_name(c), sigma)
                        )
                    case None:
                        return None
                    case cls:
                        sigmas = [sigma_ for _, sigma_ in instantiate(fields(Sigma, c), cls.args)]
                        return check_seq(qs, sigmas, p, mod_ctx)

            return bindings_at(tau, p, mod_ctx, at_disjunct)
        case _:
            assert False


def check_unbound(x: Var, p: ast.pattern, mod_ctx: ModuleContext) -> None:
    if mod_ctx.gamma.get(x) != Unbound():
        raise IllFormedModule(p, reasons.Redeclaration(x))


def check_seq(
    ps: tuple[ast.pattern, ...] | list[ast.pattern],
    taus: Sequence[Type],
    node: ast.pattern,
    mod_ctx: ModuleContext,
) -> VarContext:
    return pattern_bindings([check_pattern(q, sigma, mod_ctx) for q, sigma in zip(ps, taus)], node)


# Bindings joined over the disjuncts (check-union); a disjunct the pattern can't match binds at Never
def bindings_at(
    tau: Type,
    p: ast.pattern,
    mod_ctx: ModuleContext,
    at_disjunct: Callable[[Type], VarContext | None],
) -> VarContext:
    never: VarContext = {x: Primitive.NEVER for x in binds(p)}
    deltas = [at_disjunct(sigma) for sigma in disjuncts(tau)]
    return join_context(mod_ctx.Sigma, [never if delta is None else delta for delta in deltas])


def matched_as(tau: Type, p: ast.pattern, mod_ctx: ModuleContext) -> Type:
    Sigma = mod_ctx.Sigma
    match tau, p:
        case UnionType(sigma, sigma_), _:
            return join(Sigma, matched_as(sigma, p, mod_ctx), matched_as(sigma_, p, mod_ctx))
        case _, ast.MatchAs(pattern=None):
            return tau
        case _, ast.MatchAs(pattern=ast.pattern() as q):
            return matched_as(tau, q, mod_ctx)
        case _, ast.MatchValue() | ast.MatchSingleton():
            return meet(Sigma, LiteralType(literal_of(p)), tau)
        case TupleType(taus), PatTuple(patterns=ps) if len(taus) == len(ps):
            return TupleType(tuple(matched_as(sigma, q, mod_ctx) for sigma, q in zip(taus, ps)))
        case ListType(), PatList():
            return tau
        case DictType(), ast.MatchMapping():
            return tau
        case _, ast.MatchClass():
            cls = pattern_instance(Sigma, class_of_pattern(p, mod_ctx), tau)
            return Primitive.NEVER if cls is None else meet(Sigma, tau, cls)
        case _:
            return Primitive.NEVER


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
    # A disjunct other than a list type is above every list type or none, so list[object] stands for all
    return any(
        isinstance(sigma, ListType) or subtype(Sigma, ListType(Primitive.OBJECT), sigma)
        for sigma in disjuncts(tau)
    )


def has_tuple_values(Sigma: ClassTable, tau: Type) -> bool:
    # A disjunct other than a tuple type is above every tuple type or none, so tuple[()] stands for all
    return any(
        isinstance(sigma, TupleType) or subtype(Sigma, TupleType(()), sigma)
        for sigma in disjuncts(tau)
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
    matched, residual = result
    return tuple(form(ks) for ks in matched), tuple(form(ks) for ks in residual)


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


def join_context(Sigma: ClassTable, deltas: list[VarContext]) -> VarContext:
    return {x: join_seq(Sigma, binding_types([delta[x] for delta in deltas])) for x in deltas[0]}


def binding_types(entries: list[VarEntry]) -> list[Type]:
    types = [e for e in entries if not isinstance(e, (Unbound, DU, PU))]
    assert len(types) == len(entries)
    return types
