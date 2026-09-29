# rule: split-literal
v: int = 1
match v:
    case True:
        print("yes")
    case _:
        print("no")
