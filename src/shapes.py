from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product

from classes import Class, ClassTable
from subtyping import subtype
from type_syntax import (
    ClassType,
    DictType,
    ListType,
    LiteralType,
    Primitive,
    TupleType,
    Type,
    UnionType,
)

# A head: a literal, a class, or a length n standing for the head list_n.
type Head = LiteralType | Class | int


@dataclass(frozen=True)
class Rest:
    ty: Type
    heads: frozenset[Head]


@dataclass(frozen=True)
class Constr:
    c: Class
    args: tuple[Shape, ...]
    heads: frozenset[Head]


@dataclass(frozen=True)
class Tuple:
    components: tuple[Shape, ...]


@dataclass(frozen=True)
class List:
    elem: Type
    elems: tuple[Shape, ...]


@dataclass(frozen=True)
class Dict:
    value: Type
    bound: tuple[tuple[str, Shape], ...]
    heads: frozenset[str]


type Shape = Rest | Constr | Tuple | List | Dict
type Seq = tuple[Shape, ...]
type Shapes = tuple[Shape, ...]


def shape_type(k: Shape) -> Type:
    if isinstance(k, Rest):
        return k.ty
    if isinstance(k, Constr):
        return ClassType(k.c)
    if isinstance(k, Tuple):
        return TupleType(tuple(shape_type(c) for c in k.components))
    if isinstance(k, List):
        return ListType(k.elem)
    return DictType(k.value)


def shapes(Sigma: ClassTable, tau: Type, heads: frozenset[Head]) -> Shapes:
    if isinstance(tau, UnionType):
        left = shapes(Sigma, tau.left, typed_heads(Sigma, heads, tau.left))
        right = shapes(Sigma, tau.right, typed_heads(Sigma, heads, tau.right))
        return left + tuple(k for k in right if k not in left)
    if isinstance(tau, LiteralType) and tau in heads:
        return ()
    if tau == Primitive.BOOL and {LiteralType(True), LiteralType(False)} <= heads:
        return ()
    if tau == Primitive.NONE and LiteralType(None) in heads:
        return ()
    if isinstance(tau, ClassType) and below_excluded(Sigma, tau.c, heads):
        return ()
    if tau == Primitive.NEVER:
        return ()
    if isinstance(tau, DictType):
        assert not heads  # no head is typed at a dictionary type
        return (Dict(tau.value, (), frozenset()),)
    return (Rest(tau, heads),)


def head_typed(Sigma: ClassTable, h: Head, tau: Type) -> bool:
    if isinstance(h, Class):
        return subtype(Sigma, ClassType(h), tau)
    if isinstance(h, LiteralType):
        return subtype(Sigma, h, tau)
    return isinstance(tau, ListType)


def typed_heads(
    Sigma: ClassTable, heads: frozenset[Head], tau: Type
) -> frozenset[Head]:
    return frozenset(h for h in heads if head_typed(Sigma, h, tau))


def below_excluded(Sigma: ClassTable, c: Class, heads: frozenset[Head]) -> bool:
    return any(
        isinstance(h, Class) and subtype(Sigma, ClassType(c), ClassType(h))
        for h in heads
    )


def shapes_seq(Sigma: ClassTable, taus: Sequence[Type]) -> tuple[Seq, ...]:
    return tuple(product(*(shapes(Sigma, tau, frozenset()) for tau in taus)))
