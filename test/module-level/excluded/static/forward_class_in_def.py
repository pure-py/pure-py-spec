from dataclasses import dataclass

def make() -> int:
    return Point(7, 8).x  # Point referenced in def body, declared later

@dataclass
class Point:
    x: int
    y: int

print(make())
