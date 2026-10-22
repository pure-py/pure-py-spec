# rule: eval-binop-fail
xs: list[int] = [1]
print(xs[5] + 1 // 0)
