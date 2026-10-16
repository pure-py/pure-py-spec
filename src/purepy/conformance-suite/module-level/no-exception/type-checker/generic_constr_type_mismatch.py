from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


print(Box[str](1).value)
