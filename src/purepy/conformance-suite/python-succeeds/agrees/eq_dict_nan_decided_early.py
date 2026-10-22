# rule: eval-binop
x: float = 1e400 - 1e400
print({"a": 1, "b": x} == {"b": x, "a": 2})
