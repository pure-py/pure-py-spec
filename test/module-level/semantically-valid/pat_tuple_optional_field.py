# rule: split-class
from dataclasses import dataclass


@dataclass
class C:
    p: tuple[int, int] | None


def f(c: C) -> int:
    match c:
        case C((a, b)):
            return a + b
        case _:
            return 0


print(f(C((1, 2))))
