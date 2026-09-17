# rule: subty-list
xs: list[int] = [1]
ys: list[float] = xs  # PurePy: error (list is invariant); Python: runs
print(ys)
