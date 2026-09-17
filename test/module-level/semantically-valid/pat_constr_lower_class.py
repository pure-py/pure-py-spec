# rule: split-class
from dataclasses import dataclass


@dataclass
class C:
    n: int


@dataclass
class D(C):
    pass


def f(x: D) -> int:
    match x:
        case C(1):
            return 1
        case D(2):
            return 2
        case _:
            return 3


print(f(D(2)))
print(f(D(1)))
