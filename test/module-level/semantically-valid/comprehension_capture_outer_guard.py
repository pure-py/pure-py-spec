# rule: qual-generator
n: int = 1
print([i for i in [1, 2] if (lambda: n)() > 0])
