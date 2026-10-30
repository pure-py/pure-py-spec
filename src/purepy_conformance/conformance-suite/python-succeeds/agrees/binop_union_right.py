# rule: binop-union-right
def f(x: int | str) -> int | str:
    return 2 * x


print(f(3))
print(f("ab"))
