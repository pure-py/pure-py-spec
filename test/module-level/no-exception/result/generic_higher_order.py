from typing import Callable


def identity[T](x: T) -> T:
    return x


def twice(f: Callable[[int], int], x: int) -> int:
    return f(f(x))


print(twice(identity, 3))
g: Callable[[str], str] = identity
print(g("a"))
