# rule: split-shapes -- a pattern must match at least one shape
def f(v: list[int] | tuple[int, int]) -> int:
    match v:
        case {"k": x}:
            return x
        case _:
            return 0

print(f([1]))
