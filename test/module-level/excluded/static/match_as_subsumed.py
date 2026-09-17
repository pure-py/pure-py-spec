# rule: pat-as
v = 1
match v:
    case 1:
        print("a")
    case 1 as y:
        print("b")
