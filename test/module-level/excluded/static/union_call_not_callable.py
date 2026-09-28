# rule: call-union
from typing import Callable

def g(n: int) -> int:
    return n

def f(k: Callable[[int], int] | int) -> int:
    return k(1)

print(f(g))
