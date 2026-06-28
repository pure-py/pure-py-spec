from dataclasses import dataclass
from typing import Any

@dataclass
class Point:
    x: Any
    y: Any

p = Point(x=3, y=4)
q = Point(5, y=6)
print(p.x, p.y, q.x, q.y)
