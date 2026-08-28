# rule: seq -- captures(s) and assigns of the rest of the block must be disjoint
def g() -> int:
    return 0

h = lambda: g()

def g() -> int:  # PurePy: error (g rebound after capture by h); Python: late binding (h sees this g)
    return 1

print(h())
