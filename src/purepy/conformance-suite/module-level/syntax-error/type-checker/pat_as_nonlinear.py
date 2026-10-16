# rule: pat-as
v: tuple[int, int] = (1, 2)
match v:
    case (x, y) as x:
        print(x)
