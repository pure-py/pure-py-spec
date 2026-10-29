# rule: imp-member
from shapes import Shape, Circle, Square

def area(sh: Shape) -> int:
    match sh:
        case Circle(r):
            return 3 * r * r
        case Square(s):
            return s * s

print(area(Circle(2)))
print(area(Square(3)))
