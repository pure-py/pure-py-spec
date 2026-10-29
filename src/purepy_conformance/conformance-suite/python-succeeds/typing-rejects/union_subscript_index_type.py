# rule: subscript-union
def f(v: list[int] | dict[str, int]) -> int:
    return v[0]

print(f([1]))
