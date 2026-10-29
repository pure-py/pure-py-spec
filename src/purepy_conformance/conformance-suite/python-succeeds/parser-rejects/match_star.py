xs: list[int] = [1, 2, 3, 4]
match xs:
    case [a, *rest]:
        print(a)
        print(rest)
    case _:
        print("empty")
