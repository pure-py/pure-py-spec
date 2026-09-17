d = {"a": 1, "b": 2}
match d:
    case {"a": x}:
        print("a is")
        print(x)
    case _:
        print("other")
