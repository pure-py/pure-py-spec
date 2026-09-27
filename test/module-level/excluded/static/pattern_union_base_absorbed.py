# rule: check-constr
from dataclasses import dataclass

@dataclass
class Tree[T]:
    pass

@dataclass
class Leaf[T](Tree[T | int]):
    value: T

@dataclass
class IntLeaf(Leaf[int]):
    pass

def first(t: Tree[int]) -> int:
    match t:
        case Leaf(v):
            return 1
        case Tree():
            return 0

print(first(IntLeaf(2)))
