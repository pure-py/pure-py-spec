# rule: pat-constr-sub -- a subclass case after a superclass case matches the
# instances the superclass case left
from dataclasses import dataclass


@dataclass
class C:
    n: int


@dataclass
class D(C):
    m: str


def f(x: C) -> int:
    match x:
        case C(1):
            return 1
        case D(2, "x"):
            return 2
        case _:
            return 3


print(f(D(2, "x")))
print(f(C(1)))
print(f(D(1, "x")))
