from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


@dataclass
class Pair[T](Box[T]):
    other: T


p: Pair[int] = Pair(1, 2)
print(p.value)
print(p.other)
