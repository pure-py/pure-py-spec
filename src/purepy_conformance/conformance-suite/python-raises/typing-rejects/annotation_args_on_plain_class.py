# rule: ty-class
from dataclasses import dataclass

@dataclass
class Point:
    x: int

p: Point[int] = Point(1)
