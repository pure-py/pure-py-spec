# rule: sub-wild -- a wildcard case makes a later case unreachable
v = 1
match v:
    case _:
        print("a")
    case 1:
        print("b")
