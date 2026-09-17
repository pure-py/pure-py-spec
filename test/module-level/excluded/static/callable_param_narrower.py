# rule: subty-callable
from typing import Callable

def f(n: int) -> int:
    return n

g: Callable[[float], int] = f
print(g(1.0))
