# rule: instance-below
from dataclasses import dataclass


@dataclass
class Tree[T]:
    pass


@dataclass
class Leaf[T](Tree[T]):
    value: T


@dataclass
class IntLeaf(Leaf[int]):
    pass


def first(t: IntLeaf) -> int:
    match t:
        case Leaf(v):
            return v


print(first(IntLeaf(3)))
