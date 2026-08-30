"""Shapes, and the values each denotes.

A shape denotes a set of values of a type. The form `Rest` is a value of its
type whose head is not among those it excludes, and the others are a literal, a
constructor, a tuple, a list and a dictionary, each with shapes in place of
sub-patterns.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product

from contexts import ClassEntry, ModuleContext
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
    """Instances of `entry` or of a subclass not below `heads`, whose fields
    (those of `entry`) have the given shapes."""

    entry: ClassEntry
    args: tuple["Shape", ...]
    heads: frozenset[object]


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
        return ClassType(k.entry)
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
    if isinstance(t, ClassType) and below_excluded(t.entry, heads, ctx):
        return NOTHING
    if t == Primitive.NEVER:
        return NOTHING
    if isinstance(t, DictType):
        return frozenset(
            {Dict(t.value, (), frozenset(k for k in heads if isinstance(k, str)))}
        )
    return frozenset({Rest(t, heads)})


def head_typed(h: object, t: Type, ctx: ModuleContext) -> bool:
    """Head typing: a literal below `t`, a class below `t`, or an integer read
    as a length where `t` is a list type."""
    if isinstance(h, ClassEntry):
        return subtype(ClassType(h), t, ctx)
    if isinstance(h, LiteralType):
        return subtype(h, t, ctx)
    assert isinstance(h, int)
    return isinstance(t, ListType)


def below_excluded(
    entry: ClassEntry, heads: frozenset[object], ctx: ModuleContext
) -> bool:
    """Whether the class lies below a class of the excluded heads."""
    return any(
        isinstance(h, ClassEntry) and subtype(ClassType(entry), ClassType(h), ctx)
        for h in heads
    )


def shapes_row(ts: Sequence[Type], ctx: ModuleContext) -> frozenset[Row]:
    """Rows of shapes of the types of a row: the second form of `shapes`."""
    return frozenset(product(*(shapes(t, frozenset(), ctx) for t in ts)))
