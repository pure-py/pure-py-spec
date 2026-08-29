# rule: pat-list -- a list pattern matches only a list
v = (1, 2)
match v:
    case [a, b]:
        print(a, b)
    case _:
        print("other")
