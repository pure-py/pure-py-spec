# rule: syn-list-comp -- element type comes from the body
xs = [y * 2 for y in [1, 2, 3]]
ys: list[str] = xs
print(ys)
