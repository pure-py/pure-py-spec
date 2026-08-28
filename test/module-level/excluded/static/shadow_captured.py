# rule: seq -- captures(s) and assigns of the rest of the block must be disjoint
def f() -> int:
    x = 5
    def g() -> int:
        return x
    x = 6  # PurePy: error (reassignment of captured variable); Python: both paths see 6
    return x + g()  # 12

print(f())
