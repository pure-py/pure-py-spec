# rule: def -- the names of a mutual region must be distinct
def f():
    return 0
def g():
    return 0
def g():  # PurePy: error (duplicate name in contiguous block); Python: ok (rebinds g)
    return f()

print(g())
