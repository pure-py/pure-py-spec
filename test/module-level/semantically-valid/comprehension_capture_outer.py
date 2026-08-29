from typing import Callable

n = 3
powers: list[Callable[[int], int]] = [lambda x: x**n for i in range(10)]
print(powers[3](2))
