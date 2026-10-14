# rule: pat-dict
def f(d: dict[str, int]) -> int:
    match d:
        case {}:
            return 1
        case _:
            return 0


print(f({"a": 1}))
