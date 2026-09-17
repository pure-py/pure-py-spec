# rule: subty-callable
from typing import Callable

def f(n: int) -> float:
    return n / 2

g: Callable[[int], int] = f
print(g(1))
