# rule: match-case
from dataclasses import dataclass
from typing import Never

@dataclass
class Tree[T]:
    pass

@dataclass
class Leaf[T](Tree[Never]):
    value: T

@dataclass
class NeverTree(Tree[Never]):
    pass

def first(t: Tree[Never]) -> int:
    match t:
        case Leaf(v):
            return 1
        case Tree():
            return 0

print(first(NeverTree()))
