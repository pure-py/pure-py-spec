# rule: pat-lit -- a literal pattern matches only where its type is below the scrutinee type
v = [1, 2]
match v:
    case 1:
        print("yes")
    case _:
        print("no")
