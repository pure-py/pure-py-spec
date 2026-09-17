# rule: attr-object
xs = [1]
xs.append(2)  # PurePy: error (no rule types this); Python: appends in place
print(xs)
