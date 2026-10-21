# rule: eval-binop
x: float = 1e400 - 1e400
print({"b": x, "a": 1} == {"a": 2, "b": x})
