# rule: pat-shapes
v = (1, 2)
match v:
    case (a, b):
        print("seq")
        print(a)
        print(b)
    case (1, 2):
        print("lit")
