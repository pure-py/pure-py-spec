# rule: call
from typing import Callable

d: dict[str, Callable[[int], int]] = {"inc": lambda n: n + 1}
print(d["inc"](1))
