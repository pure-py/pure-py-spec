# list index past the end. Python raises IndexError; PurePy's eval-subscript-range gives
# fails IndexError.
xs = [1, 2, 3]
print(xs[3])
