match 42:
    case 42:
        print("forty-two")
    case _:
        print("other")

match -1:
    case -1:
        print("neg-one")

match 5:
    case x:
        print(x)

match (1, 2):
    case (a, b) as t:
        print(a, b, t)
