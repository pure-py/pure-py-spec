# rule: split-class
from dataclasses import dataclass

@dataclass
class Tree[T]:
    pass

@dataclass
class Leaf[T](Tree[T | int]):
    value: T

@dataclass
class FloatLeaf(Leaf[float]):
    pass

def first(t: Tree[float]) -> float:
    match t:
        case Leaf(v):
            return v
        case Tree():
            return 0.0

print(first(FloatLeaf(1.5)))
