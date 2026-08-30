"""Shapes, and the values each denotes.

A shape denotes a set of values of a type. The form `Rest` is a value of its
type whose head is not among those it excludes, and the others are a literal, a
constructor, a tuple, a list and a dictionary, each with shapes in place of
sub-patterns.
"""

from dataclasses import dataclass

from contexts import ModuleContext
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


@dataclass(frozen=True)
class Rest:
    """Values of type `ty` whose head is not among `heads`."""

    ty: Type
    heads: frozenset[object]


@dataclass(frozen=True)
class Literal:
    value: object


@dataclass(frozen=True)
class Constr:
    q: str
    args: tuple["Shape", ...]


@dataclass(frozen=True)
class Tuple:
    components: tuple["Shape", ...]


@dataclass(frozen=True)
class List:
    """Lists of element type `elem` whose entries have the given shapes."""

    elem: Type
    elems: tuple["Shape", ...]


@dataclass(frozen=True)
class Dict:
    """Dictionaries holding each key of `bound` with the shape it gives, and no
    key of `heads`."""

    value: Type
    bound: tuple[tuple[str, "Shape"], ...]
    heads: frozenset[str]


type Shape = Rest | Literal | Constr | Tuple | List | Dict
type Row = tuple[Shape, ...]

NOTHING: frozenset[Shape] = frozenset()


def shape_type(k: Shape) -> Type:
    """Least type of a shape."""
    if isinstance(k, Rest):
        return k.ty
    if isinstance(k, Literal):
        return LiteralType(k.value)
    if isinstance(k, Constr):
        return ClassType(k.q)
    if isinstance(k, Tuple):
        return TupleType(tuple(shape_type(c) for c in k.components))
    if isinstance(k, List):
        return ListType(k.elem)
    return DictType(k.value)


def shapes(t: Type, heads: frozenset[object], ctx: ModuleContext) -> frozenset[Shape]:
    """Shapes of `t` that remain once the heads in `heads` are excluded."""
    if isinstance(t, UnionType):
        return shapes(t.left, heads, ctx) | shapes(t.right, heads, ctx)
    if isinstance(t, LiteralType) and t in heads:
        return NOTHING
    if t == Primitive.BOOL and {LiteralType(True), LiteralType(False)} <= heads:
        return NOTHING
    if t == Primitive.NONE and LiteralType(None) in heads:
        return NOTHING
    if isinstance(t, ClassType) and any(
        isinstance(h, str) and subtype(t, ClassType(h), ctx) for h in heads
    ):
        return NOTHING
    if t == Primitive.NEVER:
        return NOTHING
    if isinstance(t, DictType):
        return frozenset(
            {Dict(t.value, (), frozenset(k for k in heads if isinstance(k, str)))}
        )
    return frozenset({Rest(t, heads)})
