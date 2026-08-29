# rule: split-shapes -- a tuple pattern matches only a tuple shape of the same length
v = [1, 2]
match v:
    case (a, b):
        print(a)
        print(b)
    case _:
        print("other")
