# rule: ty-list
list = 5
x: list[int] = [1]  # PurePy: error (list shadowed); Python: TypeError
print(x)
