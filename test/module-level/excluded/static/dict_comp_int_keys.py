# rule: syn-dict-comp
xs: list[int] = [1, 2, 3]
print({x: x + 1 for x in xs})
