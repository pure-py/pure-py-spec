# rule: binop -- bool is not an int, so arithmetic has no signature for it
x: bool = True
print(x + 1)
