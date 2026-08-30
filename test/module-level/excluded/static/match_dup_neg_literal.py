# rule: split-rest-literal -- a negative literal case leaves nothing for the same literal
v = -1
match v:
    case -1:
        print("a")
    case -1:
        print("b")
