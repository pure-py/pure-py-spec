# rule: sub-as-l -- an as-pattern is unreachable when its inner pattern is subsumed
v = 1
match v:
    case 1:
        print("a")
    case 1 as y:
        print("b")
