# rule: check-dict-none
def f(o: object) -> int:
    match o:
        case {"a": x}:
            return x
        case _:
            return 0


print(f({"a": 1}))
