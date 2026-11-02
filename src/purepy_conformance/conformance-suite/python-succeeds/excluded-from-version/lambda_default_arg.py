from typing import Callable

f: Callable[[], int] = lambda x=1: x
print(f())
