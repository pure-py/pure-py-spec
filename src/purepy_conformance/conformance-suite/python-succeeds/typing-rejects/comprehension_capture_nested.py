# rule: list-comp
from typing import Callable

fs: list[list[Callable[[], int]]] = [[lambda: i for j in [1]] for i in [1]]
print(fs[0][0]())
