# rule: lambda -- the body checks against the result type
from typing import Callable

f: Callable[[int], str] = lambda x: x + 1
print(f(2))
