from dataclasses import dataclass
from typing import Any

def make():
    return Point(7, 8)  # Point referenced in def body, declared later

@dataclass
class Point:
    x: Any
    y: Any

p = make()
print(p.x, p.y)
