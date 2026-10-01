# rule: match-partial
from dataclasses import dataclass


@dataclass
class C:
    p: tuple[int, int] | None


def f(c: C) -> int:
    match c:
        case C(None):
            return 0
        case C((a, b)):
            return a + b
    return -1


print(f(C((1, 2))))
print(f(C(None)))
