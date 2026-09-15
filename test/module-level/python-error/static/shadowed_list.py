# rule: ty-list -- list must still be the builtin where an annotation names it
list = 5
x: list[int] = [1]  # PurePy: error (list shadowed); Python: TypeError
print(x)
