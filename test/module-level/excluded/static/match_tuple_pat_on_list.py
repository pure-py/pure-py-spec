# rule: cases-cons -- a tuple pattern agrees with no list type
v = [1, 2]
match v:
    case (a, b):
        print(a)
        print(b)
    case _:
        print("other")
