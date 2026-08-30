# rule: split-rest-list -- a list case leaves nothing for the same list pattern
v = [1, 2]
match v:
    case [a, b]:
        print("a")
    case [c, d]:
        print("b")
    case _:
        print("c")
