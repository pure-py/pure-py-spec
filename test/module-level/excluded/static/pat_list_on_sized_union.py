# rule: check-list-none
from typing import Sized


def f(s: Sized | list[int]) -> int:
    match s:
        case [a, b]:
            return a
        case _:
            return 0


print(f([1, 2]))
