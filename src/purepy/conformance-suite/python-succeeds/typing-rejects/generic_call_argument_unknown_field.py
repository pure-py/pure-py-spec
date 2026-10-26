# rule: callee-scheme
from dataclasses import dataclass


@dataclass
class P:
    x: int


def first[T](x: T) -> T:
    return x


def g(p: P) -> int:
    return first(p.y)


print(0)
