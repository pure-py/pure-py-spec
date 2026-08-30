# rule: subty-callable -- callables are related only where their components are equivalent
from typing import Callable

def f(n: int) -> int:
    return n

g: Callable[[int], float] = f  # PurePy: error (callables are invariant); Python: runs
print(g(1))
