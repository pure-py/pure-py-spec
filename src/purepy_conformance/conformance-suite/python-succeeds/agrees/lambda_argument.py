# rule: lambda
from typing import Callable

def apply(f: Callable[[int], int]) -> int:
    return f(1)

print(apply(lambda x: x + 1))
