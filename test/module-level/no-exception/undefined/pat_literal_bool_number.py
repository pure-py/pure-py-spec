# rule: eval-match-undef
x: object = True
match x:
    case 1:
        print("one")
    case _:
        print("no match")
