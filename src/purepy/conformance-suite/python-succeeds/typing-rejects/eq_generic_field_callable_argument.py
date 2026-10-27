# rule: binop
from dataclasses import dataclass
from typing import Callable


@dataclass
class Box[T]:
    x: T


def f(n: int) -> int:
    return n


print(Box[Callable[[int], int]](f) == Box[Callable[[int], int]](f))
