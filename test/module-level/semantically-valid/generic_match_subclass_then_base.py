# rule: split-subclass
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    extra: str

def unbox(b: Box[int]) -> Box[int]:
    return b

def describe(b: Box[int]) -> str:
    match b:
        case IntBox(v, e):
            return e
        case Box(v):
            return "box"

print(describe(unbox(IntBox(1, "a"))))
