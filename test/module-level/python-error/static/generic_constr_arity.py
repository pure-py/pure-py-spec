from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


print(Box[int, str](1).value)
