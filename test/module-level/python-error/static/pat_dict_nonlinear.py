d = {"a": 1, "b": 2}
match d:
    case {"a": x, "b": x}:
        print(x)
    case _:
        print("other")
