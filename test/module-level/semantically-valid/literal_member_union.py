# rule: subty-union-left -- a literal type is below a union with that literal as a member
from typing import Literal

x: Literal[1] | str = 1
print(x)
