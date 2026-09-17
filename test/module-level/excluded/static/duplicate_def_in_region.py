# rule: def
def f() -> int:
    return 0
def g() -> int:
    return 0
def g() -> int:
    return f()

print(g())
