# rule: match-case
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    pass

@dataclass
class Wrap:
    inner: object

def first(w: Wrap) -> int:
    match w:
        case Wrap(Box(v)):
            return 1
        case _:
            return 0

print(first(Wrap(IntBox(1))))
