from dataclasses import dataclass
from typing import Any
@dataclass
class P:
    x: Any
p = P(1)
p.x = 2
print(p.x)
