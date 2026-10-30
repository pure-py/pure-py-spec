# rule: instance-below
from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


@dataclass
class Pair[T](Box[T]):
    other: T


def first[T](p: Pair[T]) -> T:
    return p.value


b: Box[int] = Box(1)
print(first(b))
