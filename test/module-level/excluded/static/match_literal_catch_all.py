# rule: match -- a case the literal-typed scrutinee cannot reach is rejected
x = 42
match x:
    case 42:
        print("forty-two")
    case _:
        print("other")
