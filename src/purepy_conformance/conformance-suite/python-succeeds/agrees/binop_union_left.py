# rule: binop-union-left
def f(x: int | str) -> int | str:
    return x * 2


print(f(3))
print(f("ab"))
