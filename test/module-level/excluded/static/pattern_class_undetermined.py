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

def first(o: object) -> int:
    match o:
        case Box(v):
            return 1
        case _:
            return 0

print(first(IntBox(1, "a")))
