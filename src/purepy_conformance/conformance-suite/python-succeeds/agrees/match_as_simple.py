# rule: check-as
x: int = 42
match x:
    case n as m:
        print(n)
        print(m)
