# rule: type-alias
from dataclasses import dataclass

@dataclass
class Circle:
    r: int

@dataclass
class Square:
    s: int

type Shape = Circle | Square

def area(sh: Shape) -> int:
    match sh:
        case Circle(r):
            return 3 * r * r
        case Square(s):
            return s * s

print(area(Circle(2)))
print(area(Square(3)))
