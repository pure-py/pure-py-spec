d = {"name": "alice", "age": 30}
match d:
    case {"name": n, "age": a}:
        print(n, a)
    case _:
        print("other")
