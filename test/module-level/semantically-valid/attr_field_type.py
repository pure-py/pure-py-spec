# rule: attr-object
from dataclasses import dataclass

@dataclass
class Point:
    x: int

def negate(n: int) -> int:
    return -n

p = Point(1)
print(negate(p.x))
