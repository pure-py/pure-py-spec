# rule: class (top-down, no forward refs at module top level)
from dataclasses import dataclass

p = Point(1, 2)  # Point not yet declared

@dataclass
class Point:
    x: int
    y: int
