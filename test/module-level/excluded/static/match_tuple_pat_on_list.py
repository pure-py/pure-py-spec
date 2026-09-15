# rule: case -- a tuple pattern is not sequence-safe at a list type
v = [1, 2]
match v:
    case (a, b):
        print(a)
        print(b)
    case _:
        print("other")
