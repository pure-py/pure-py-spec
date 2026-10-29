# rule: ty-name
from typing import Never

xs: list[Never] = []
print(len(xs))
