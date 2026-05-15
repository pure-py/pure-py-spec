def g():
    return 0

def f():
    return g()
def g():  # PurePy: error (reassignment of g, captured by f); Python: late binding (f sees this g)
    return 1

print(f())
