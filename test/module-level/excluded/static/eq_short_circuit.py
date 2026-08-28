from typing import Callable

def f(n: int) -> int:
    return n

a: tuple[int, Callable[[int], int]] = (1, f)
b: tuple[int, Callable[[int], int]] = (2, f)
print(a == b)
