# rule: split-shapes -- a literal pattern matches only where its type is below the shape's
v = 5
match v:
    case "x":
        print("yes")
    case _:
        print("no")
