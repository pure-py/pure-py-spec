from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


print(Box(1).value)
