# rule: pat-union -- a pattern must match at least one alternative
def f(v: list[int] | tuple[int, int]) -> int:
    match v:
        case {"k": x}:
            return x
        case _:
            return 0

print(f([1]))
