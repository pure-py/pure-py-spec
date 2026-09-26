# rule: split-class
from dataclasses import dataclass

@dataclass
class Tree[T]:
    pass

@dataclass
class Leaf[T](Tree[int]):
    value: T

@dataclass
class IntTree(Tree[int]):
    pass

def first(t: Tree[int]) -> int:
    match t:
        case Leaf(v):
            return 1
        case Tree():
            return 0

print(first(IntTree()))
