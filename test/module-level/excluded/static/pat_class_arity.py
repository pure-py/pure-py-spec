# rule: pat-constr
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(1, 2)
match p:
    case Point():  # PurePy: error (under-saturated); Python: ok (matches any Point)
        pass
