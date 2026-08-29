from dataclasses import dataclass

@dataclass
class Empty:
    pass

@dataclass
class Point:
    x: int
    y: int

Empty()
p = Point(1, 2)
print(p.x)
print(p.y)
