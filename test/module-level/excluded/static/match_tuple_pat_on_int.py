# rule: split-shapes -- a tuple pattern matches only a tuple shape of the same length
v = 5
match v:
    case (a, b):
        print(a, b)
    case _:
        print("nope")
