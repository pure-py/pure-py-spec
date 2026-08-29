import shapes
p = shapes.Point(5, 6)
match p:
    case shapes.Point(x, y):
        print(x, y)
