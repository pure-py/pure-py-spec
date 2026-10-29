# rule: split-class
from dataclasses import dataclass

@dataclass
class Tree[T]:
    pass

@dataclass
class Leaf[T](Tree[T | int]):
    value: T

@dataclass
class StrTree(Tree[str]):
    pass

def first(t: Tree[str]) -> int:
    match t:
        case Leaf(v):
            return 1
        case Tree():
            return 0

print(first(StrTree()))
