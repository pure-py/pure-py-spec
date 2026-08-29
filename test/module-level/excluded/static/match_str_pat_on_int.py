# rule: pat-lit -- a literal pattern matches only where its type is below the scrutinee type
v = 5
match v:
    case "x":
        print("yes")
    case _:
        print("no")
