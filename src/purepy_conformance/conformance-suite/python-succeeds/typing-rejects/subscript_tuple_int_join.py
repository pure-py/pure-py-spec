# judgement: subtyping, rule: subty-union
def f(t: tuple[int, str], i: int) -> int:
    return t[i]


print(f((1, "a"), 0))
