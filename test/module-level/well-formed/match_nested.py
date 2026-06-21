v = (1, [2, 3])
match v:
    case (a, [b, c]):
        print(a, b, c)
    case _:
        print("other")
