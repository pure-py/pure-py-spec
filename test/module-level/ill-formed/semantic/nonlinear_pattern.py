from typing import Any
from dataclasses import dataclass

@dataclass
class C:
    a: Any
    b: Any

p = C(1, 2)
match p:
    case C(x, x):
        pass
