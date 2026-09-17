# rule: qual-generator
def f(xs: list[int] | list[str]) -> int:
    return len([x for x in xs])

print(f([1, 2]))
print(f(["a"]))
