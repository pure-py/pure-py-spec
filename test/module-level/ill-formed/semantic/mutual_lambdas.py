# rule: var
f = lambda x: 0 if x == 0 else g(x - 1)  # PurePy: error (g not yet assigned); Python: late binding
g = lambda x: 0 if x == 0 else f(x - 1)

print(f(3))
