# rule: eval-binop
x: float = 1e400 - 1e400
print([1, x] == [2, x])
print([x] == [x, x])
print(1 in [1, x])
