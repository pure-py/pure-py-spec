from typing import Callable

def f(n: int) -> int:
    g: Callable[[int], int] = lambda x: x + n
    return g(1)

print(f(10))
