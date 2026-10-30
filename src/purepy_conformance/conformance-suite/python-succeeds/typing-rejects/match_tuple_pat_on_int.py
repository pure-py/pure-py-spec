# rule: pat-shapes
v: int = 5
match v:
    case (a, b):
        print(a)
        print(b)
    case _:
        print("nope")
