# rule: pat-shapes -- a list pattern matches only a list shape
v = (1, 2)
match v:
    case [a, b]:
        print(a)
        print(b)
    case _:
        print("other")
