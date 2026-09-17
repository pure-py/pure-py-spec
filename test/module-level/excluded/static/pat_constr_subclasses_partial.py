# rule: def
from dataclasses import dataclass

@dataclass
class Shape:
    n: int

@dataclass
class Circle(Shape):
    r: int

@dataclass
class Square(Shape):
    s: int

def f(v: Shape) -> int:
    match v:
        case Circle(n, r):
            return r
        case Square(n, s):
            return s

print(f(Circle(1, 2)))
print(f(Square(1, 3)))
