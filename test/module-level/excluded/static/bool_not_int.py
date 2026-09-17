# rule: subty-literal
x: int = True  # PurePy: error (bool is not an int); Python: runs
print(x)
