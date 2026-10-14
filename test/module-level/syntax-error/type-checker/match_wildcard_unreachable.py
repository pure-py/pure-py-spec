# rule: pat-wild
v: int = 1
match v:
    case _:
        print("a")
    case 1:
        print("b")
