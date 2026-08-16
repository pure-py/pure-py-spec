d = {1: "a"}
match d:
    case {1: x}:
        print(x)
    case _:
        print("other")
