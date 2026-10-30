# rule: subscript-union
def f(v: list[int] | int) -> int:
    return v[0]

print(f([1]))
