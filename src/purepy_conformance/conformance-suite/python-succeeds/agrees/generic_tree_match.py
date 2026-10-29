# rule: split-class
from dataclasses import dataclass

@dataclass
class Tree[T]:
    pass

@dataclass
class Leaf[T](Tree[T]):
    value: T

@dataclass
class Node[T](Tree[T]):
    left: Tree[T]
    right: Tree[T]

@dataclass
class IntLeaf(Leaf[int]):
    pass

@dataclass
class IntNode(Node[int]):
    pass

def total(t: Tree[int]) -> int:
    match t:
        case Leaf(v):
            return v
        case Node(l, r):
            return total(l) + total(r)
        case Tree():
            return 0

print(total(IntNode(IntLeaf(1), IntNode(IntLeaf(2), IntLeaf(3)))))
