v = (1, 2)
match v:
    case (a, b) as t:
        print(a, b, t)
    case _:
        print("other")
