# rule: pat-dict -- a key an earlier case bound is matched against the shape recorded for it
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
