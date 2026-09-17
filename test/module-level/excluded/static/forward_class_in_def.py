from dataclasses import dataclass

def make() -> int:
    return Point(7, 8).x

@dataclass
class Point:
    x: int
    y: int

print(make())
