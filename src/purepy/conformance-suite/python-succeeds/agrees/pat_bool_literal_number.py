# rule: eval-match
x: object = 1
match x:
    case True:
        print("true")
    case _:
        print("no match")
