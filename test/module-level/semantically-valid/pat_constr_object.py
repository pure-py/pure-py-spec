# rule: split-class -- a class pattern meets an object scrutinee at the class
from dataclasses import dataclass


@dataclass
class C:
    n: int


def f(x: object) -> int:
    match x:
        case C(n):
            return n
        case _:
            return 0


print(f(C(7)))
print(f(3))
