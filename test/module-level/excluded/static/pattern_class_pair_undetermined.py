# rule: split-class
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    extra: str

def unbox(b: Box[int]) -> Box[int]:
    return b

@dataclass
class Pair[A, B](Box[A]):
    second: B

def first(b: Box[int]) -> int:
    match b:
        case Pair(a, s):
            return a
        case Box(v):
            return v

print(first(IntBox(1, "a")))
