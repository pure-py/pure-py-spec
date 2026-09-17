d = {"a": 1}
match d:
    case {"a": x, "a": y}:
        print(x)
        print(y)
    case _:
        print("other")
