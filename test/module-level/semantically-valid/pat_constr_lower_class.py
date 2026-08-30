# rule: pat-rest-constr -- expansion takes the lower of the shape's type and
# the pattern's class, so a later case for the type itself can match
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
