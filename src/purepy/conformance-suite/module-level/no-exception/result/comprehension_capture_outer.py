from typing import Callable

n: int = 3
powers: list[Callable[[int], float]] = [lambda x: x**n for i in [1, 2, 3, 4]]
print(powers[3](2))
