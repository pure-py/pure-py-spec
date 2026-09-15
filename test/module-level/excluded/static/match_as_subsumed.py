# rule: pat-as -- a case matching nothing the earlier cases leave is rejected
v = 1
match v:
    case 1:
        print("a")
    case 1 as y:
        print("b")
