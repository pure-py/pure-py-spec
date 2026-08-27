from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(1, z=2)
print(p)
