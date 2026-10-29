# rule: pat-shapes
from dataclasses import dataclass


@dataclass
class Left:
    x: int


@dataclass
class Right:
    y: int


def f(v: Left | Right) -> int:
    match v:
        case Left(a):
            return a
        case r:
            return r.y


print(f(Left(1)))
print(f(Right(2)))
