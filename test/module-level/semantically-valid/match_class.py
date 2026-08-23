from dataclasses import dataclass
from typing import Any

@dataclass
class Point:
    x: Any
    y: Any

p = Point(0, 1)
match p:
    case Point(x, y):
        print(x, y)
    case _:
        print("other")
