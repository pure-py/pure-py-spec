# rule: def
from typing import Callable

def g() -> int:
    return 0

h: Callable[[], int] = lambda: g()

def g() -> int:
    return 1

print(h())
