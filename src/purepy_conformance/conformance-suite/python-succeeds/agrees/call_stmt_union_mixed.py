# rule: call-stmt-union
from typing import Callable


def f(k: Callable[[int], None] | Callable[[int], int]) -> None:
    k(1)


def g(n: int) -> int:
    return n


f(g)
print(g(1))
