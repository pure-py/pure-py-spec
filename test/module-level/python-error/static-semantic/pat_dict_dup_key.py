d = {"a": 1}
match d:
    case {"a": x, "a": y}:
        print(x, y)
    case _:
        print("other")
