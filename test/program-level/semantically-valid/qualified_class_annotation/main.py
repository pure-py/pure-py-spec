# rule: ty-class -- a class name in an annotation may be qualified
import shapes

p: shapes.Point = shapes.Point(3, 4)
print(p.x)
