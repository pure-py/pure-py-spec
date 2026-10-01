from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


print(Box(lambda n: n).value(1))
