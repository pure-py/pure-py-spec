def f(n):
    if n == 0:
        return 0
    return g(n - 1)

c = 100  # PurePy: error (assignment splits mutual block of {f, g}); Python: ok

def g(n):
    if n == 0:
        return c
    return f(n - 1)

print(f(5))
