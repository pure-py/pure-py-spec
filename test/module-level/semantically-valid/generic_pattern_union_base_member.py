# rule: split-class
from dataclasses import dataclass

@dataclass
class Tree[T]:
    pass

@dataclass
class Leaf[T](Tree[list[T] | int]):
    value: T

@dataclass
class StrLeaf(Leaf[str]):
    pass

def first(t: Tree[int | list[str]]) -> str:
    match t:
        case Leaf(v):
            return v
        case Tree():
            return ""

print(first(StrLeaf("a")))
