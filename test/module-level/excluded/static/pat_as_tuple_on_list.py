# rule: check-as
v: list[int] = [1, 2]
match v:
    case (a, b) as t:
        print(t)
    case _:
        print("other")
