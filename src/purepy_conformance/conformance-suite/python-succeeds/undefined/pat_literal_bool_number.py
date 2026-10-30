# rule: eval-match-abort
x: object = True
match x:
    case 1:
        print("one")
    case _:
        print("no match")
