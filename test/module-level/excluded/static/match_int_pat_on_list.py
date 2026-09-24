# rule: pat-shapes
v: list[int] = [1, 2]
match v:
    case 1:
        print("yes")
    case _:
        print("no")
