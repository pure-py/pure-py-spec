from typing import Callable


def apply[A, B](f: Callable[[A], B], x: A) -> B:
    return f(x)


print(apply(lambda n: n + 1, 1))
