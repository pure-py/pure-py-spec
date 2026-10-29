# rule: ty-alias
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    extra: str

type Boxed = Box[int]

b: Boxed = IntBox(1, "a")
print(b.value)
