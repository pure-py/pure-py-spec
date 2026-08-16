d = {"a": 1, "b": 2}
match d:
    case {"a": x, **rest}:
        print(x, rest)
    case _:
        print("other")
