from dataclasses import dataclass
from typing import Any

@dataclass
class Empty:
    pass

@dataclass
class Point:
    x: Any
    y: Any

Empty()
p = Point(1, 2)
print(p.x, p.y)
