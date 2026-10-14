# rule: binop
def f(x: int | str) -> int:
    return x + 1

print(f(1))
