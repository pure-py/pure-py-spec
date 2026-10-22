# rule: lambda
from typing import Callable

f: Callable[[int], str] = lambda x: x + 1
print(f(2))
