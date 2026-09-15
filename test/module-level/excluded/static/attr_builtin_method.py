# rule: attr-object -- an attribute reference needs an object of a class type
xs = [1]
xs.append(2)  # PurePy: error (no rule types this); Python: appends in place
print(xs)
