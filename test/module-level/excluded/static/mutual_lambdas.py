# rule: var -- a name used in a lambda body must be definitely assigned
from typing import Callable

f: Callable[[int], int] = lambda x: 0 if x == 0 else g(x - 1)  # PurePy: error (g not yet assigned); Python: late binding
g: Callable[[int], int] = lambda x: 0 if x == 0 else f(x - 1)

print(f(3))
