# rule: eval-match-abort
x: int | bool = True
match x:
    case 1:
        print("one")
    case _:
        print("no match")
