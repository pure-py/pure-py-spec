# rule: pat-shapes
v = 5
match v:
    case "x":
        print("yes")
    case _:
        print("no")
