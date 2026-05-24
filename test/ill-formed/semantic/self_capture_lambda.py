# rule: assign
f = lambda n: 0 if n == 0 else f(n - 1)  # PurePy: error (f not definitely assigned); Python: late binding
print(f(3))
