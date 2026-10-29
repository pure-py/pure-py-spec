# rule: var
from typing import Callable
f: Callable[[int], int] = lambda n: 0 if n == 0 else f(n - 1)
print(f(3))
