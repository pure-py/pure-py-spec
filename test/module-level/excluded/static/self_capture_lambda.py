# rule: assign
f = lambda n: 0 if n == 0 else f(n - 1)
print(f(3))
