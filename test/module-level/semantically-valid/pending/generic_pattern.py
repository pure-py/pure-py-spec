from dataclasses import dataclass


@dataclass
class Box[T]:
    value: T


@dataclass
class IntBox(Box[int]):
    pass


match IntBox(1):
    case Box(v):
        print(v)
