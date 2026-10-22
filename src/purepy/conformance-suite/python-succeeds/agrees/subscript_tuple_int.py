# rule: subscript-tuple-int
def f(t: tuple[int, str], i: int) -> int | str:
    return t[i]

print(f((1, "a"), 1))
