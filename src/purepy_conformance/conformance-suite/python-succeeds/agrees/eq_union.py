# rule: binop
def f(x: int | str) -> bool:
    return x == 1

print(f(1))
print(f("a"))
