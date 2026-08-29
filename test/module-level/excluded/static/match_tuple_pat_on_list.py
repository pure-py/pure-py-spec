# rule: pat-tuple -- a tuple pattern matches only a tuple of the same length
v = [1, 2]
match v:
    case (a, b):
        print(a, b)
    case _:
        print("other")
