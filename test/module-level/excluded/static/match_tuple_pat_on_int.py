# rule: pat-tuple -- a tuple pattern matches only a tuple of the same length
v = 5
match v:
    case (a, b):
        print(a, b)
    case _:
        print("nope")
