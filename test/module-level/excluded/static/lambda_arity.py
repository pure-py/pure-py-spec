# rule: lambda -- one parameter type for each parameter
from typing import Callable

f: Callable[[int, int], int] = lambda x: x
print(f(1))
