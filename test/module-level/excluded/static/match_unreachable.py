# rule: pat-shapes
v: tuple[int, int] = (1, 2)
match v:
    case (a, b):
        print("seq")
        print(a)
        print(b)
    case (1, 2):
        print("lit")
