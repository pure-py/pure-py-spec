from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


b: Box[int | str] = Box[int | str]("a")
print(b.value)
