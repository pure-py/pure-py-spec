# rule: binop
def f(x: int | float) -> float:
    return x + 1


print(f(1))
print(f(1.5))
