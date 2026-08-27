from dataclasses import dataclass

def make():
    return Point(7, 8)  # Point referenced in def body, declared later

@dataclass
class Point:
    x: int
    y: int

p = make()
print(p.x, p.y)
