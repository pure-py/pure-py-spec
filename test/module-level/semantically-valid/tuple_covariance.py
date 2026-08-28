# rule: subty-tuple -- a tuple is immutable, so its type is covariant
def first(t: tuple[int, str]) -> int:
    return t[0]

print(first((1, "a")))
