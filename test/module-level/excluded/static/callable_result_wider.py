# rule: subty-callable -- results do not widen
from typing import Callable

def f(n: int) -> float:
    return n / 2

g: Callable[[int], int] = f  # PurePy: error (float result is not an int); Python: runs
print(g(1))
