from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(x=3, y=4)
q = Point(5, y=6)
print(p.x)
print(p.y)
print(q.x)
print(q.y)
