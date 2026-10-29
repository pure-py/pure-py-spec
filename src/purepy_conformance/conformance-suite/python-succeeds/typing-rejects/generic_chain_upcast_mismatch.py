# rule: subty-class-extend
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class Tagged[T](Box[T]):
    tag: str

@dataclass
class IntTagged(Tagged[int]):
    count: int

b: Box[str] = IntTagged(1, "one", 3)
print(b.value)
