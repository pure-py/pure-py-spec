# rule: split-dict
d: dict[str, int] = {"a": 1}
match d:
    case {"a": x, "c": y}:
        print(x)
        print(y)
    case _:
        print("no c")
