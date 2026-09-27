# rule: check-constr
from dataclasses import dataclass
from typing import Never

@dataclass
class Box[T]:
    value: T

def first(x: Never) -> int:
    match x:
        case Box(v):
            return 1
        case _:
            return 0

print(0)
