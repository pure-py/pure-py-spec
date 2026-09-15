# rule: subty-list -- lists are related only where their element types are equivalent
xs: list[int] = [1]
ys: list[float] = xs  # PurePy: error (list is invariant); Python: runs
print(ys)
