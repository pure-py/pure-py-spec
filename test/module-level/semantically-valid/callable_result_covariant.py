# rule: subty-callable
from typing import Callable

def f(n: int) -> int:
    return n

g: Callable[[int], float] = f
print(g(1))
