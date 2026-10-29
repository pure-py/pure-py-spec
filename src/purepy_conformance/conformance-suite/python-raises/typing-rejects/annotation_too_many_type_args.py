# rule: ty-class
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    extra: str

x: Box[int, str] = IntBox(1, "a")
