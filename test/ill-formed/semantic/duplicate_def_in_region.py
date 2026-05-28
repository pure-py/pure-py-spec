# rule: mutual
def f():
    return 0
def g():
    return 0
def g():  # PurePy: error (duplicate name in contiguous block); Python: ok (rebinds g)
    return f()

print(g())
