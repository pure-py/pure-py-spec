d = {"a": 1}
match d:
    case {"a": x, "c": y}:
        print(x, y)
    case _:
        print("no c")
