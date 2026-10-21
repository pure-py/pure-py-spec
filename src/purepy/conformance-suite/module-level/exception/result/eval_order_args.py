# rule: eval-exprs-fail
def f(a: int, b: int) -> int:
    return a + b


xs: list[int] = [1]
print(f(xs[5], 1 // 0))
