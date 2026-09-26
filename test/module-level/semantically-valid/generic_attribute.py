# rule: attr-object
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    extra: str

def unbox(b: Box[int]) -> Box[int]:
    return b

x: Box[int] = unbox(IntBox(1, "a"))
print(x.value + 1)
