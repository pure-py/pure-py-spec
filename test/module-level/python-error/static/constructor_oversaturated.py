# rule: constr -- too many positional arguments
from dataclasses import dataclass
@dataclass
class Point:
    x: int
    y: int
p = Point(1, 2, 3)
