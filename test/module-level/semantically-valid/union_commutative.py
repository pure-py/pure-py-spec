# rule: subty-list
def f(xs: list[int | str]) -> list[str | int]:
    return xs

print(f([1, "a"]))
