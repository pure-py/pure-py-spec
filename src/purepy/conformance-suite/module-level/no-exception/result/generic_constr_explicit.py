from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


print(Box[int](1).value)
