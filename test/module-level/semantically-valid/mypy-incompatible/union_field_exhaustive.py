# rule: split-class -- one shape per member of a union field, so the cases
# exhaust it; mypy wants a catch-all
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


print(f(C((1, 2))))
print(f(C(None)))
