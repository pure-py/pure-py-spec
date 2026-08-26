# method of a built-in value. Python appends in place; PurePy has no rule for an
# attribute reference on a list, so evaluation is stuck.
xs = [1]
xs.append(2)
print(xs)
