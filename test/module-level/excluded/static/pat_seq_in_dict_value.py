# rule: match-case -- a dictionary pattern is sequence-safe only if each value pattern is, at the value type
def f(d: dict[str, list[int] | tuple[int, int]]) -> int:
    match d:
        case {"k": (a, b)}:
            return a
        case _:
            return 0


print(f({"k": [1, 2]}))
