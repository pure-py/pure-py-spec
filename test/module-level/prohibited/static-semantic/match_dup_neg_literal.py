# rule: sub-neg-lit -- a repeated negative-literal pattern is unreachable
v = -1
match v:
    case -1:
        print("a")
    case -1:
        print("b")
