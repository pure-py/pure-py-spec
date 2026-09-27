# rule: check-constr
from dataclasses import dataclass

@dataclass
class Box[T]:
    value: T

@dataclass
class IntBox(Box[int]):
    pass

def first(o: Box[int] | object) -> int:
    match o:
        case Box(v):
            return 1
        case _:
            return 0

print(first(IntBox(1)))
