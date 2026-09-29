# rule: qual-generator
print([i for i in [1, 2] if (lambda: i)() > 1])
