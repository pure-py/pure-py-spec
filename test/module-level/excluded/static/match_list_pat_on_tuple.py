# rule: split-shapes -- a list pattern matches only a list shape
v = (1, 2)
match v:
    case [a, b]:
        print(a, b)
    case _:
        print("other")
