# rule: constr
from dataclasses import dataclass
@dataclass
class Point:
    x: int
    y: int
p: Point = Point(1, 2, 3)
