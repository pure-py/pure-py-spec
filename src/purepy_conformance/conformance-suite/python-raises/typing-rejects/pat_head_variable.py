# rule: check-constr
x: int = 3
match 1:
    case x():
        print(0)
