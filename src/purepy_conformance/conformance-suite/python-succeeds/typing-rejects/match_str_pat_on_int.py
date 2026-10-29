# rule: pat-shapes
v: int = 5
match v:
    case "x":
        print("yes")
    case _:
        print("no")
