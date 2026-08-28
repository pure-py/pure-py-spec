# rule: constr
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(1, "b")
print(p.y)
