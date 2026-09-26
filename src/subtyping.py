from collections.abc import Sequence
from dataclasses import dataclass

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
    alphas = Sigma[c].type_params
    match tau:
        case ClassType(d, _):
            if c in ancestors(Sigma, d):
                return instantiated_ancestor(Sigma, tau, c)
            if d not in ancestors(Sigma, c):
                return None
            generic = ClassType(c, tuple(TypeVariable(alpha) for alpha in alphas))
            bindings: dict[Var, Type] = {}
            if not match_type(
                Sigma, instantiated_ancestor(Sigma, generic, d), tau, alphas, bindings
            ):
                return None
            if any(alpha not in bindings for alpha in alphas):
                return Undetermined()
            return ClassType(c, tuple(bindings[alpha] for alpha in alphas))
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


def match_type(
    Sigma: ClassTable, sigma: Type, tau: Type, alphas: Sequence[Var], bindings: dict[Var, Type]
) -> bool:
    """Bind the type variables alphas of sigma so that sigma becomes tau, up to equivalence."""
    match (sigma, tau):
        case (TypeVariable(alpha), _) if alpha in alphas:
            if alpha in bindings:
                return equivalent(Sigma, bindings[alpha], tau)
            bindings[alpha] = tau
            return True
        case (ListType(sigma_), ListType(tau_)) | (DictType(sigma_), DictType(tau_)):
            return match_type(Sigma, sigma_, tau_, alphas, bindings)
        case (TupleType(sigmas), TupleType(taus)):
            return len(sigmas) == len(taus) and all(
                match_type(Sigma, a, b, alphas, bindings) for a, b in zip(sigmas, taus)
            )
        case (CallableType(sigmas, sigma_), CallableType(taus, tau_)):
            return (
                len(sigmas) == len(taus)
                and all(match_type(Sigma, a, b, alphas, bindings) for a, b in zip(sigmas, taus))
                and match_type(Sigma, sigma_, tau_, alphas, bindings)
            )
        case (ClassType(c, sigmas), ClassType(d, taus)):
            return c == d and all(
                match_type(Sigma, a, b, alphas, bindings) for a, b in zip(sigmas, taus)
            )
        case (UnionType(sigma1, sigma2), UnionType(tau1, tau2)):
            return match_type(Sigma, sigma1, tau1, alphas, bindings) and match_type(
                Sigma, sigma2, tau2, alphas, bindings
            )
        case _:
            return equivalent(Sigma, sigma, tau)
