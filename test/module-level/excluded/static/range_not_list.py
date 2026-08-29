# rule: check-synth -- a range is not a list
xs: list[int] = range(5)  # PurePy: error (range is not a list); Python: runs
print(len(xs))
