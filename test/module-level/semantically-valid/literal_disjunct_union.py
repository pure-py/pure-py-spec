# rule: subty-union-left
from typing import Literal

x: Literal[1] | str = 1
print(x)
