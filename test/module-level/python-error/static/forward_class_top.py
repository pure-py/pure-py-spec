# rule: class
from dataclasses import dataclass

p = Point(1, 2)  # Point not yet declared

@dataclass
class Point:
    x: int
    y: int
