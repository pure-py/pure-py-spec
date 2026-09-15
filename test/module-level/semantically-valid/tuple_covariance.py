# rule: subty-tuple
def first(t: tuple[int, str]) -> int:
    return t[0]

print(first((1, "a")))
