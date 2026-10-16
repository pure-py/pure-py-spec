v: tuple[int, list[int]] = (1, [2, 3])
match v:
    case (a, [b, c]):
        print(a)
        print(b)
        print(c)
    case _:
        print("other")
