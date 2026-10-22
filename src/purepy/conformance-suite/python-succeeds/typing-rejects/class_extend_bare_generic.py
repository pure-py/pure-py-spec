# rule: class-extend
from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


@dataclass
class IntBox(Box):
    extra: str


print(IntBox(1, "a").extra)
