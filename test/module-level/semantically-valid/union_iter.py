# rule: qual-generator -- elem-type of a union is the join of the element types
def f(xs: list[int] | list[str]) -> int:
    return len([x for x in xs])

print(f([1, 2]))
print(f(["a"]))
