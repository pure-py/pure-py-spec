# rule: subty-callable
from typing import Callable

def f(x: float) -> int:
    return 1

g: Callable[[int], int] = f
print(g(2))
