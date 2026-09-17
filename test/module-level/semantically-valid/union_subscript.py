# rule: subscript-union
def f(xs: list[int] | list[str]) -> int | str:
    return xs[0]

print(f([1]))
print(f(["a"]))
