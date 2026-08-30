# rule: subty-refl -- lists are related only by reflexivity
xs: list[int] = [1]
ys: list[float] = xs  # PurePy: error (list is invariant); Python: runs
print(ys)
