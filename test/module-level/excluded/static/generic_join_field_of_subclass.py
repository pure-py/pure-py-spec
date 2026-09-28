# rule: syn-cond
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    extra: str

def unbox(b: Box[int]) -> Box[int]:
    return b

def pick(c: bool) -> str:
    return (unbox(IntBox(1, "a")) if c else IntBox(2, "b")).extra

print(pick(False))
