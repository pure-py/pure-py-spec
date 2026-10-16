import shapes
p: shapes.Point = shapes.Point(5, 6)
match p:
    case shapes.Point(x, y):
        print(x)
        print(y)
