# rule: binop-union-left
def f(x: int | None) -> int:
    return x + 1


print(f(None))
