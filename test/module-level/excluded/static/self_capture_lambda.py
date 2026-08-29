# rule: assign
f = lambda n: 0 if n == 0 else f(n - 1)  # PurePy: error (f captured by its own right-hand side); Python: late binding
print(f(3))
