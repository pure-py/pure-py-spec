# rule: class-extend
from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


@dataclass
class Pair(Box[int, int]):
    pass


print(Pair(1).value)
