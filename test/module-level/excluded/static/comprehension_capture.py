# rule: list-comp
from typing import Callable
powers: list[Callable[[int], int]] = [lambda x: x**i for i in [1, 2, 3]]
print(powers[2](2))
