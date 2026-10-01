from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


b: Box[int] = Box(1)
print(b.value)
