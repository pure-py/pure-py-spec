# rule: match-case
from typing import Sized


def f(s: Sized | tuple[int, int]) -> int:
    match s:
        case (a, b):
            return a
        case _:
            return 0


print(f((1, 2)))
