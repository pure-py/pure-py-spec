# rule: pat-constr
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p: Point = Point(1, 2)
match p:
    case Point():
        pass
