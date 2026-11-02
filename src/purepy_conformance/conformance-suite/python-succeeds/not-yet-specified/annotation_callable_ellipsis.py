from typing import Callable

f: Callable[..., int] = lambda: 1
print(f())
