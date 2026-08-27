# rule: sub-constr -- patterns for unrelated classes do not subsume each other
from dataclasses import dataclass
from typing import Any

@dataclass
class Left:
    x: Any

@dataclass
class Right:
    y: Any

def describe(v: Any) -> Any:
    match v:
        case Left(a):
            return a
        case Right(b):
            return b
        case _:
            return 0

print(describe(Left(1)))
print(describe(Right(2)))
