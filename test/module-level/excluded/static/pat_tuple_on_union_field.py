# rule: case -- a constructor pattern is sequence-safe only if each sub-pattern is, at the declared type of its field
from dataclasses import dataclass


@dataclass
class C:
    s: list[int] | tuple[int, int]


def f(c: C) -> int:
    match c:
        case C((a, b)):
            return a
        case _:
            return 0


print(f(C([1, 2])))
