# rule: binop
from dataclasses import dataclass
from typing import Callable

@dataclass
class C:
    f: Callable[[int], int]

def g(n: int) -> int:
    return n

print(C(g) == C(g))
