# rule: syn-list-comp
xs: list[int] = [1 for y in [1]] + [2]
print(xs)
