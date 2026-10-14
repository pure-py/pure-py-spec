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
class StrBox(Box[str]):
    pass

def first(b: Box[str]) -> int:
    match b:
        case IntBox(v, e):
            return v
        case Box(v):
            return 0

print(first(StrBox("s")))
