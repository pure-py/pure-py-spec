# rule: seq
def f():
    x = 5
    def g():
        return x
    x = 6  # PurePy: error (reassignment of captured variable); Python: both paths see 6
    return x + g()  # 12

print(f())
