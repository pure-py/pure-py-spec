# rule: constr -- a constructor argument is checked against the field type
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(1, "b")
print(p.y)
