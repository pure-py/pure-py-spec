# rule: ty-class
from dataclasses import dataclass

p: Point = Point(1, 2)

@dataclass
class Point:
    x: int
    y: int
