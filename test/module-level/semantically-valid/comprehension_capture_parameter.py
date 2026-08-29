from typing import Callable

powers: list[Callable[[int], float]] = [(lambda i: (lambda x: x**i))(i) for i in range(10)]
print(powers[3](2))
