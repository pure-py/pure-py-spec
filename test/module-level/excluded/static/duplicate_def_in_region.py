# rule: def -- the names of a mutual region must be distinct
def f() -> int:
    return 0
def g() -> int:
    return 0
def g() -> int:  # PurePy: error (duplicate name in contiguous block); Python: ok (rebinds g)
    return f()

print(g())
