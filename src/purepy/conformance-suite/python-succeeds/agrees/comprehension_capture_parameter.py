from typing import Callable

powers: list[Callable[[int], float]] = [(lambda i: (lambda x: x**i))(i) for i in [1, 2, 3, 4]]
print(powers[3](2))
