from dataclasses import dataclass
from typing import Any

value = 1

@dataclass
class value:  # allowed: the name held a variable, not a class
    x: Any

v = value(2)
print(v.x)
