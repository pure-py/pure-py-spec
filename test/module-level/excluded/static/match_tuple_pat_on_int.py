# rule: pat-shapes
v = 5
match v:
    case (a, b):
        print(a)
        print(b)
    case _:
        print("nope")
