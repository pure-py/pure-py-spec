# rule: call
from dataclasses import dataclass
from typing import Callable


@dataclass
class C:
    x: int


def f(C: Callable[[int], int]) -> int:
    return C(1)


print(f(lambda n: n + 1))
print(C(2).x)
