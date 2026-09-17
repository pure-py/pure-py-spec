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
    if isinstance(sigma, UnionType):
        return join(Sigma, meet(Sigma, sigma.left, tau), meet(Sigma, sigma.right, tau))
    if isinstance(tau, UnionType):
        return join(Sigma, meet(Sigma, sigma, tau.left), meet(Sigma, sigma, tau.right))
    if (
        isinstance(sigma, TupleType)
        and isinstance(tau, TupleType)
        and len(sigma.components) == len(tau.components)
    ):
        return TupleType(
            tuple(meet(Sigma, a, b) for a, b in zip(sigma.components, tau.components))
        )
    if (
        isinstance(sigma, CallableType)
        and isinstance(tau, CallableType)
        and len(sigma.params) == len(tau.params)
    ):
        return CallableType(
            tuple(join(Sigma, a, b) for a, b in zip(sigma.params, tau.params)),
            meet(Sigma, sigma.result, tau.result),
        )
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
    if isinstance(sigma, UnionType):
        return subtype(Sigma, sigma.left, tau) and subtype(Sigma, sigma.right, tau)
    if isinstance(tau, UnionType):
        return subtype(Sigma, sigma, tau.left) or subtype(Sigma, sigma, tau.right)
    if isinstance(sigma, LiteralType):
        return subtype(Sigma, base_type(sigma.value), tau)
    if tau == Primitive.SIZED:
        return (
            isinstance(sigma, (ListType, DictType, TupleType)) or sigma == Primitive.STR
        )
    if isinstance(sigma, ClassType) and isinstance(tau, ClassType):
        return tau.c in ancestors(Sigma, sigma.c)
    if isinstance(sigma, TupleType) and isinstance(tau, TupleType):
        return len(sigma.components) == len(tau.components) and all(
            subtype(Sigma, a, b) for a, b in zip(sigma.components, tau.components)
        )
    if isinstance(sigma, ListType) and isinstance(tau, ListType):
        return equivalent(Sigma, sigma.tau, tau.tau)
    if isinstance(sigma, DictType) and isinstance(tau, DictType):
        return equivalent(Sigma, sigma.value, tau.value)
    if isinstance(sigma, CallableType) and isinstance(tau, CallableType):
        return (
            len(sigma.params) == len(tau.params)
            and all(subtype(Sigma, b, a) for a, b in zip(sigma.params, tau.params))
            and subtype(Sigma, sigma.result, tau.result)
        )
    return False


def equivalent(Sigma: ClassTable, sigma: Type, tau: Type) -> bool:
    return subtype(Sigma, sigma, tau) and subtype(Sigma, tau, sigma)


def comparable(Sigma: ClassTable, sigma: Type, tau: Type) -> bool:
    return subtype(Sigma, sigma, tau) or subtype(Sigma, tau, sigma)
