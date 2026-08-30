# rule: subty-list -- element types equivalent up to the order of a union
def f(xs: list[int | str]) -> list[str | int]:
    return xs

print(f([1, "a"]))
