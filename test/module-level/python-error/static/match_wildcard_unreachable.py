# rule: pat-wild -- a wildcard case leaves nothing for a later case
v = 1
match v:
    case _:
        print("a")
    case 1:
        print("b")
