# rule: check-constr-none
from dataclasses import dataclass


@dataclass
class Left:
    x: int


@dataclass
class Right:
    y: int


def f(v: Left) -> int:
    match v:
        case Right(b):
            return b
        case _:
            return 0


print(f(Left(1)))
