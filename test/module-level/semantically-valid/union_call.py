# rule: call-union -- a call of a union of callables synthesises the join over the members
from typing import Callable

def g(n: int) -> int:
    return n

def h(n: int) -> str:
    return "s"

def f(k: Callable[[int], int] | Callable[[int], str]) -> int | str:
    return k(1)

print(f(g))
print(f(h))
