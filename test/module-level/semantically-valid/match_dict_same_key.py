# rule: pat-dict
def f(d: dict[str, int]) -> int:
    match d:
        case {"a": 1}:
            return 1
        case {"a": x}:
            return x
        case _:
            return 0

print(f({"a": 1}))
print(f({"a": 5}))
print(f({}))
