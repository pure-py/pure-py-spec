# rule: pat-rest-constr -- a case for an unrelated class leaves the others
from dataclasses import dataclass

@dataclass
class Left:
    x: int

@dataclass
class Right:
    y: int

def describe(v: Left | Right) -> int:
    match v:
        case Left(a):
            return a
        case Right(b):
            return b

print(describe(Left(1)))
print(describe(Right(2)))
