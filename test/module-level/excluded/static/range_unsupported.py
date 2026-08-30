# rule: var -- range is not a member of builtins
xs = [i * 2 for i in range(4)]  # PurePy: error; Python: [0, 2, 4, 6]
print(xs)
