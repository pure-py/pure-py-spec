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
# Sets of heads and of keys are frozen so that a shape is hashable.
type Heads = frozenset[Head]
type Keys = frozenset[str]


@dataclass(frozen=True)
class Rest:
    ty: Type
    hs: Heads


@dataclass(frozen=True)
class Constr:
    c: Class
    args: ShapeSeq
    hs: Heads


@dataclass(frozen=True)
class Tuple:
    components: ShapeSeq


@dataclass(frozen=True)
class List:
    elem: Type
    elems: ShapeSeq


@dataclass(frozen=True)
class Dict:
    value: Type
    beta: KeyShapes
    hs: Keys


type Shape = Rest | Constr | Tuple | List | Dict
# The spec's beta, a finite map from keys to shapes, as sorted pairs so a shape is hashable.
type KeyShapes = tuple[tuple[str, Shape], ...]
type ShapeSeq = tuple[Shape, ...]
type ShapeSeqs = tuple[ShapeSeq, ...]
type Shapes = tuple[Shape, ...]


def shape_type(k: Shape) -> Type:
    match k:
        case Rest(tau, _):
            return tau
        case Constr(c, _, _):
            return ClassType(c)
        case Tuple(ks):
            return TupleType(tuple(shape_type(c) for c in ks))
        case List(tau, _):
            return ListType(tau)
        case Dict(tau, _, _):
            return DictType(tau)


def shapes(Sigma: ClassTable, tau: Type, hs: Heads) -> Shapes:
    if isinstance(tau, UnionType):
        left = shapes(Sigma, tau.left, typed_heads(Sigma, hs, tau.left))
        right = shapes(Sigma, tau.right, typed_heads(Sigma, hs, tau.right))
        return left + tuple(k for k in right if k not in left)
    if isinstance(tau, LiteralType) and tau in hs:
        return ()
    if tau == Primitive.BOOL and {LiteralType(True), LiteralType(False)} <= hs:
        return ()
    if tau == Primitive.NONE and LiteralType(None) in hs:
        return ()
    if isinstance(tau, ClassType) and below_excluded(Sigma, tau.c, hs):
        return ()
    if tau == Primitive.NEVER:
        return ()
    if isinstance(tau, DictType):
        assert len(hs) == 0  # no head is typed at a dictionary type
        return (Dict(tau.value, (), frozenset()),)
    return (Rest(tau, hs),)


def head_typed(Sigma: ClassTable, h: Head, tau: Type) -> bool:
    match h:
        case Class():
            return subtype(Sigma, ClassType(h), tau)
        case LiteralType():
            return subtype(Sigma, h, tau)
        case int():
            return isinstance(tau, ListType)


def typed_heads(Sigma: ClassTable, hs: Heads, tau: Type) -> Heads:
    return frozenset(h for h in hs if head_typed(Sigma, h, tau))


def below_excluded(Sigma: ClassTable, c: Class, hs: Heads) -> bool:
    return any(
        isinstance(h, Class) and subtype(Sigma, ClassType(c), ClassType(h)) for h in hs
    )


def shapes_seq(Sigma: ClassTable, taus: Sequence[Type]) -> ShapeSeqs:
    return tuple(product(*(shapes(Sigma, tau, frozenset()) for tau in taus)))
