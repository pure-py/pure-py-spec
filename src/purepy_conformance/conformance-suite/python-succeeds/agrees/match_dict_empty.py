# rule: pat-dict
def f(d: dict[str, int]) -> int:
    match d:
        case {}:
            return len(d)

print(f({"a": 1}))
