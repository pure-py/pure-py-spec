# rule: sub-list-list -- a repeated list pattern is unreachable
v = [1, 2]
match v:
    case [a, b]:
        print("a")
    case [c, d]:
        print("b")
    case _:
        print("c")
