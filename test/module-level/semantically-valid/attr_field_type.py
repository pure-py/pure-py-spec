# rule: attr-object -- an attribute reference has the field's declared type
from dataclasses import dataclass

@dataclass
class Point:
    x: int

def negate(n: int) -> int:
    return -n

p = Point(1)
print(negate(p.x))
