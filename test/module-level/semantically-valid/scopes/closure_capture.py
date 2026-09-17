from typing import Callable
def outer(x: int) -> Callable[[int], Callable[[int], int]]:
    def middle(y: int) -> Callable[[int], int]:
        def inner(z: int) -> int:
            return x + y + z
        return inner
    return middle

print(outer(1)(2)(3))
