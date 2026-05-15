def g():
    return 0

h = lambda: g()

def g():  # PurePy: error (g rebound after capture by h); Python: late binding (h sees this g)
    return 1

print(h())
