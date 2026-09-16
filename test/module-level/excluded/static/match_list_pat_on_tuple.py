# rule: match-case -- a list pattern is not sequence-safe at a tuple type
v = (1, 2)
match v:
    case [a, b]:
        print(a)
        print(b)
    case _:
        print("other")
