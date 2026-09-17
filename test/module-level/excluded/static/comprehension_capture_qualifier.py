# rule: qual-generator
fs = [f for i in [0, 1, 2] for f in [lambda: i]]
print([f() for f in fs])
