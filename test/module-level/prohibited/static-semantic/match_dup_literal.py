# rule: sub-lit -- a repeated literal pattern is unreachable
v = 1
match v:
    case 1:
        print("a")
    case 1:
        print("b")
