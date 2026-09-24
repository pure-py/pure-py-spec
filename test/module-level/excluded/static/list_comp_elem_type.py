# rule: syn-list-comp
xs: list[int] = [y * 2 for y in [1, 2, 3]]
ys: list[str] = xs
print(ys)
