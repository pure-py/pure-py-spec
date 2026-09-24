# rule: match-case
v: tuple[int, int] = (1, 2)
match v:
    case [a, b]:
        print(a)
        print(b)
    case _:
        print("other")
