# rule: callee-scheme
from typing import Callable


def identity[U](u: U) -> U:
    return u


def apply[T](f: Callable[[T], T], x: T) -> T:
    return f(x)


print(apply(identity, 1))
