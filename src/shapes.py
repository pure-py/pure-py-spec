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
    """Values of type `ty` whose head is not among `heads`."""

    ty: Type
    heads: frozenset[Head]


@dataclass(frozen=True)
class Constr:
    """Instances of `c` or of a subclass not below `heads`, whose fields (those
    of `c`) have the given shapes."""

    c: Class
    args: tuple["Shape", ...]
    heads: frozenset[Head]


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


type Shape = Rest | Constr | Tuple | List | Dict
type Seq = tuple[Shape, ...]

NOTHING: tuple[Shape, ...] = ()


def shape_type(k: Shape) -> Type:
    """Least type of a shape."""
    if isinstance(k, Rest):
        return k.ty
    if isinstance(k, Constr):
        return ClassType(k.c)
    if isinstance(k, Tuple):
        return TupleType(tuple(shape_type(c) for c in k.components))
    if isinstance(k, List):
        return ListType(k.elem)
    return DictType(k.value)


def shapes(sigma: ClassTable, t: Type, heads: frozenset[Head]) -> tuple[Shape, ...]:
    """Shapes of `t` that remain once the heads in `heads` are excluded."""
    if isinstance(t, UnionType):
        left = shapes(sigma, t.left, typed_heads(sigma, heads, t.left))
        right = shapes(sigma, t.right, typed_heads(sigma, heads, t.right))
        return left + tuple(k for k in right if k not in left)
    if isinstance(t, LiteralType) and t in heads:
        return NOTHING
    if t == Primitive.BOOL and {LiteralType(True), LiteralType(False)} <= heads:
        return NOTHING
    if t == Primitive.NONE and LiteralType(None) in heads:
        return NOTHING
    if isinstance(t, ClassType) and below_excluded(sigma, t.c, heads):
        return NOTHING
    if t == Primitive.NEVER:
        return NOTHING
    if isinstance(t, DictType):
        assert not heads  # no head is typed at a dictionary type
        return (Dict(t.value, (), frozenset()),)
    return (Rest(t, heads),)


def head_typed(sigma: ClassTable, h: Head, t: Type) -> bool:
    """Head typing: a literal or class below `t`, or a length where `t` is a
    list type."""
    if isinstance(h, Class):
        return subtype(sigma, ClassType(h), t)
    if isinstance(h, LiteralType):
        return subtype(sigma, h, t)
    return isinstance(t, ListType)


def typed_heads(sigma: ClassTable, heads: frozenset[Head], t: Type) -> frozenset[Head]:
    """The heads typed at `t`, kept when an excluded set passes to a shape of a
    narrower type."""
    return frozenset(h for h in heads if head_typed(sigma, h, t))


def below_excluded(sigma: ClassTable, c: Class, heads: frozenset[Head]) -> bool:
    """Whether the class lies below a class of the excluded heads."""
    return any(
        isinstance(h, Class) and subtype(sigma, ClassType(c), ClassType(h))
        for h in heads
    )


def shapes_seq(sigma: ClassTable, ts: Sequence[Type]) -> tuple[Seq, ...]:
    """Sequences of shapes of a sequence of types: the second form of `shapes`."""
    return tuple(product(*(shapes(sigma, t, frozenset()) for t in ts)))
