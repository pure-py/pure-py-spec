from collections.abc import Sequence

from classes import ClassTable, ancestors
from type_syntax import (
    CallableType,
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
    base_type,
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
            return join(
                Sigma, meet(Sigma, sigma.left, tau), meet(Sigma, sigma.right, tau)
            )
        case (_, UnionType()):
            return join(
                Sigma, meet(Sigma, sigma, tau.left), meet(Sigma, sigma, tau.right)
            )
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
            return subtype(Sigma, base_type(sigma.value), tau)
        case (ClassType(c), ClassType(d)):
            return d in ancestors(Sigma, c)
        case (TupleType(sigmas), TupleType(taus)):
            return len(sigmas) == len(taus) and all(
                subtype(Sigma, a, b) for a, b in zip(sigmas, taus)
            )
        case (ListType(sigma_), ListType(tau_)):
            return equivalent(Sigma, sigma_, tau_)
        case (DictType(sigma_), DictType(tau_)):
            return equivalent(Sigma, sigma_, tau_)
        case (CallableType(sigmas, sigma_), CallableType(taus, tau_)):
            return (
                len(sigmas) == len(taus)
                and all(subtype(Sigma, b, a) for a, b in zip(sigmas, taus))
                and subtype(Sigma, sigma_, tau_)
            )
        case _:
            if tau == Primitive.SIZED:
                return (
                    isinstance(sigma, (ListType, DictType, TupleType))
                    or sigma == Primitive.STR
                )
            return False


def equivalent(Sigma: ClassTable, sigma: Type, tau: Type) -> bool:
    return subtype(Sigma, sigma, tau) and subtype(Sigma, tau, sigma)


def comparable(Sigma: ClassTable, sigma: Type, tau: Type) -> bool:
    return subtype(Sigma, sigma, tau) or subtype(Sigma, tau, sigma)
