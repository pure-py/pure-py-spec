# rule: subscript-union -- a subscript of a union synthesises the join over the members
def f(xs: list[int] | list[str]) -> int | str:
    return xs[0]

print(f([1]))
print(f(["a"]))
