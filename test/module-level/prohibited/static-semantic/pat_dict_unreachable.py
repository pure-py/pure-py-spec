d = {"a": 1}
match d:
    case {"a": x}:
        print(x)
    case {"a": 1, "b": y}:
        print(y)
    case _:
        print("other")
