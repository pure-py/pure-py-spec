# rule: ty-imported -- Sized must be imported to be written
x: Sized = [1, 2]
print(len(x))
