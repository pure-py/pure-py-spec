d: dict[str, str] = {1: "a"}
match d:
    case {1: x}:
        print(x)
    case _:
        print("other")
