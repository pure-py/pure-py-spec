# rule: match
from dataclasses import dataclass


@dataclass
class D:
    n: int


@dataclass
class C:
    d: D
    p: tuple[int, int] | None


def f(c: C) -> int:
    match c:
        case C(D(0), _):
            return 0
        case C(D(x), _):
            return x


print(f(C(D(0), None)))
print(f(C(D(7), (1, 2))))
