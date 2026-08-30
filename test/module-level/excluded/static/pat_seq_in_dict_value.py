# rule: cases-cons -- a value pattern agrees at the dictionary's value type
def f(d: dict[str, list[int] | tuple[int, int]]) -> int:
    match d:
        case {"k": (a, b)}:
            return a
        case _:
            return 0


print(f({"k": [1, 2]}))
