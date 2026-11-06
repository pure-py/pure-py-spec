# judgement: stmt, rule: declare-assign
from typing import Callable

def f(n: int) -> int:
    return n

g: Callable[[int, int], int] = f
print(0)
