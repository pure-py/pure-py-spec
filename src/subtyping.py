from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product

from classes import Class, ClassTable, ancestors
from type_syntax import (
    CallableType,
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    TypeVariable,
    UnionType,
    Var,
    base_type,
    render,
    substitute,
)


def join(Sigma: ClassTable, sigma: Type, tau: Type) -> Type:
    if subtype(Sigma, sigma, tau):
        return tau
    if subtype(Sigma, tau, sigma):
        return sigma
    return UnionType(sigma, tau)


def meet(Sigma: ClassTable, sigma: Type, tau: Type) -> Type:
    if subtype(Sigma, sigma, tau):
        return sigma
    if subtype(Sigma, tau, sigma):
        return tau
    match (sigma, tau):
        case (UnionType(), _):
            return join(Sigma, meet(Sigma, sigma.left, tau), meet(Sigma, sigma.right, tau))
        case (_, UnionType()):
            return join(Sigma, meet(Sigma, sigma, tau.left), meet(Sigma, sigma, tau.right))
        case (TupleType(sigmas), TupleType(taus)):
            return (
                TupleType(tuple(meet(Sigma, a, b) for a, b in zip(sigmas, taus)))
                if len(sigmas) == len(taus)
                else Primitive.NEVER
            )
        case (CallableType(sigmas, sigma_), CallableType(taus, tau_)):
            return (
                CallableType(
                    tuple(join(Sigma, a, b) for a, b in zip(sigmas, taus)),
                    meet(Sigma, sigma_, tau_),
                )
                if len(sigmas) == len(taus)
                else Primitive.NEVER
            )
        case _:
            return Primitive.NEVER


def join_seq(Sigma: ClassTable, taus: Sequence[Type]) -> Type:
    if len(taus) == 0:
        return Primitive.NEVER
    return join(Sigma, taus[0], join_seq(Sigma, taus[1:]))


def subtype(Sigma: ClassTable, sigma: Type, tau: Type) -> bool:
    if sigma == tau or sigma == Primitive.NEVER or tau == Primitive.OBJECT:
        return True
    if sigma == Primitive.INT and tau == Primitive.FLOAT:
        return True
    match (sigma, tau):
        case (UnionType(), _):
            return subtype(Sigma, sigma.left, tau) and subtype(Sigma, sigma.right, tau)
        case (_, UnionType()):
            return subtype(Sigma, sigma, tau.left) or subtype(Sigma, sigma, tau.right)
        case (LiteralType(), _):
            return subtype(Sigma, base_type(sigma), tau)
        case (ClassType(c, taus), ClassType(d, sigmas)):
            if c == d and all(equivalent(Sigma, a, b) for a, b in zip(taus, sigmas)):
                return True
            base = Sigma[c].base
            return base is not None and subtype(
                Sigma, substitute(taus, Sigma[c].type_params, base), tau
            )
        case (TupleType(sigmas), TupleType(taus)):
            return len(sigmas) == len(taus) and all(
                subtype(Sigma, a, b) for a, b in zip(sigmas, taus)
            )
        case (ListType(sigma_), ListType(tau_)) | (DictType(sigma_), DictType(tau_)):
            return equivalent(Sigma, sigma_, tau_)
        case (CallableType(sigmas, sigma_), CallableType(taus, tau_)):
            return (
                len(sigmas) == len(taus)
                and all(subtype(Sigma, b, a) for a, b in zip(sigmas, taus))
                and subtype(Sigma, sigma_, tau_)
            )
        case _:
            if tau == Primitive.SIZED:
                return isinstance(sigma, (ListType, DictType, TupleType)) or sigma == Primitive.STR
            return False


def equivalent(Sigma: ClassTable, sigma: Type, tau: Type) -> bool:
    return subtype(Sigma, sigma, tau) and subtype(Sigma, tau, sigma)


def comparable(Sigma: ClassTable, sigma: Type, tau: Type) -> bool:
    return subtype(Sigma, sigma, tau) or subtype(Sigma, tau, sigma)


@dataclass(frozen=True)
class Undetermined:
    pass


def instance(Sigma: ClassTable, c: Class, tau: Type) -> ClassType | Undetermined | None:
    above = instance_above(Sigma, c, tau)
    return above if above is not None else instance_below(Sigma, c, tau)


def instance_above(Sigma: ClassTable, c: Class, tau: Type) -> ClassType | Undetermined | None:
    match tau:
        case ClassType(d, _) if c in ancestors(Sigma, d):
            return instantiated_ancestor(Sigma, tau, c)
        case Primitive.NEVER:
            return ClassType(c, ()) if len(Sigma[c].type_params) == 0 else Undetermined()
        case _:
            return None


def instance_below(Sigma: ClassTable, c: Class, tau: Type) -> ClassType | Undetermined | None:
    assert not isinstance(tau, UnionType)  # instances are taken at the disjuncts of a union
    alphas = Sigma[c].type_params
    match tau:
        case ClassType(d, sigmas) if d in ancestors(Sigma, c):
            generic = ClassType(c, tuple(TypeVariable(alpha) for alpha in alphas))
            rhos = instantiated_ancestor(Sigma, generic, d).args
            match solutions(Sigma, rhos, sigmas, alphas):
                case []:
                    return None
                case [taus]:
                    return ClassType(c, taus)
                case _:
                    return Undetermined()
        case Primitive.OBJECT:
            return ClassType(c, ()) if len(alphas) == 0 else Undetermined()
        case _:
            return None


def instantiated_ancestor(Sigma: ClassTable, tau: ClassType, d: Class) -> ClassType:
    """Instantiation of ancestor d of tau's class reached along the base classes."""
    while tau.c != d:
        base = Sigma[tau.c].base
        assert base is not None
        sigma = substitute(tau.args, Sigma[tau.c].type_params, base)
        assert isinstance(sigma, ClassType)
        tau = sigma
    return tau


def solutions(
    Sigma: ClassTable, rhos: Sequence[Type], sigmas: Sequence[Type], alphas: Sequence[Var]
) -> list[tuple[Type, ...]]:
    """Instantiations of alphas making rhos equivalent to sigmas, pairwise inequivalent, at most two.
    The variables range over unions of the non-union subterms of sigmas and object."""
    atoms = sorted(
        {a for sigma in sigmas for a in non_union_subterms(sigma)} | {Primitive.OBJECT}, key=render
    )
    candidates = (
        tuple(join_seq(Sigma, ts) for ts in choice)
        for choice in product(subsets(atoms), repeat=len(alphas))
    )
    solving = (
        taus
        for taus in candidates
        if all(
            equivalent(Sigma, substitute(taus, alphas, rho), sigma)
            for rho, sigma in zip(rhos, sigmas)
        )
    )
    first = next(solving, None)
    if first is None:
        return []
    second = next((taus for taus in solving if not equivalent_seq(Sigma, taus, first)), None)
    return [first] if second is None else [first, second]


def equivalent_seq(Sigma: ClassTable, sigmas: Sequence[Type], taus: Sequence[Type]) -> bool:
    return all(equivalent(Sigma, sigma, tau) for sigma, tau in zip(sigmas, taus))


def disjuncts(tau: Type) -> list[Type]:
    match tau:
        case UnionType(sigma, sigma_):
            return disjuncts(sigma) + disjuncts(sigma_)
        case _:
            return [tau]


def non_union_subterms(tau: Type) -> set[Type]:
    match tau:
        case UnionType(sigma, sigma_):
            return non_union_subterms(sigma) | non_union_subterms(sigma_)
        case ListType(sigma) | DictType(sigma):
            return {tau} | non_union_subterms(sigma)
        case TupleType(sigmas) | ClassType(_, sigmas):
            return {tau}.union(*(non_union_subterms(sigma) for sigma in sigmas))
        case CallableType(sigmas, sigma):
            return {tau}.union(non_union_subterms(sigma), *(non_union_subterms(s) for s in sigmas))
        case _:
            return {tau}


def subsets[T](xs: Sequence[T]) -> list[tuple[T, ...]]:
    return [
        tuple(x for x, keep in zip(xs, keeps) if keep)
        for keeps in product((False, True), repeat=len(xs))
    ]
