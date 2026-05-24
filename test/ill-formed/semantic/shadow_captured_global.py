# rule: seq
x = 6
def g():
    return x
x = 7  # PurePy: error (reassignment of captured variable); Python: g sees 7
print(g())
