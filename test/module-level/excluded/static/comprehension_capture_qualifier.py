# rule: qual-generator -- a lambda in a later qualifier may not capture a generator variable
fs = [f for i in [0, 1, 2] for f in [lambda: i]]
print([f() for f in fs])  # PurePy: error; Python: [2, 2, 2]
