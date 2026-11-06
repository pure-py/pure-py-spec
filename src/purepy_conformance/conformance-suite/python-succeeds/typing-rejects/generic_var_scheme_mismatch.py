# judgement: subtyping, rule: subty-callable
from typing import Callable


def identity[T](x: T) -> T:
    return x


g: Callable[[str], int] = identity
print(g("a"))
