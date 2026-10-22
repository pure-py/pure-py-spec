# rule: callee-scheme
from typing import Callable


def apply[A](f: Callable[[A], A], x: A) -> A:
    return f(x)


print(apply(lambda n: n + 1, 1))
