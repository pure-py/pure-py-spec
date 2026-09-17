# rule: split-list
v = [1, 2]
match v:
    case [a, b]:
        print("a")
    case [c, d]:
        print("b")
    case _:
        print("c")
