from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


print(Box(value=1).value)
