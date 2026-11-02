from typing import Callable


def twice(f: Callable[[int], int]) -> Callable[[int], int]:
    return lambda x: f(f(x))


@twice
def inc(x: int) -> int:
    return x + 1


print(inc(1))
