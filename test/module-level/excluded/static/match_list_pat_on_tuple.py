# rule: match -- a list pattern agrees with no tuple type
v = (1, 2)
match v:
    case [a, b]:
        print(a)
        print(b)
    case _:
        print("other")
