# rule: def-signature
from dataclasses import dataclass

def make() -> Point:
    return Point(1)

@dataclass
class Point:
    x: int

print(make().x)
