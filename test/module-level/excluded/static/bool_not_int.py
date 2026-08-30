# rule: subty-literal -- bool is not below int
x: int = True  # PurePy: error (bool is not an int); Python: runs
print(x)
