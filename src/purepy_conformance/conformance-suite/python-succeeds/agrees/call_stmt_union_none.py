# rule: call-stmt-union
from typing import Callable


def f(k: Callable[[int], None] | Callable[[float], None]) -> None:
    k(1)


def g(n: int) -> None:
    print(n)


f(g)
