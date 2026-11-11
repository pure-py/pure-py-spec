# rule: eval-binop
def f(x: int) -> int:
    return x


g: object = f
print(g == g)
print([1][2])
