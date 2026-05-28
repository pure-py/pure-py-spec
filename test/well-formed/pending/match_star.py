xs = [1, 2, 3, 4]
match xs:
    case [a, *rest]:
        print(a, rest)
    case _:
        print("empty")
