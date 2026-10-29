# rule: qual-generator
def f(v: list[int] | int) -> int:
    return len([x for x in v])

print(f([1]))
