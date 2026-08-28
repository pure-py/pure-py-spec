from typing import Callable

def f(n: int) -> int:
    return n

def g(n: int) -> int:
    return n + 1

a: tuple[int, Callable[[int], int]] = (1, f)
b: tuple[int, Callable[[int], int]] = (1, g)
print(a == b)
