from typing import Callable

f: Callable[[int], int] = lambda x: x + 1
print(f(2))
