# rule: pat-dict-nil -- the empty pattern matches every dictionary, so it alone exhausts a dictionary type
def f(d: dict[str, int]) -> int:
    match d:
        case {}:
            return len(d)

print(f({"a": 1}))
