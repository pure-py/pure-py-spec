# rule: class-extend
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    extra: str

b: IntBox = IntBox(1, "a")
print(b.value + 1)
print(b.extra)
