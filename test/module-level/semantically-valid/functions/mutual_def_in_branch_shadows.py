b = True

def g() -> int:
    return 0

if b:
    def f() -> int:
        return g()  # sibling g, bound simultaneously, not the outer g
    def g() -> int:
        return 1
    print(f())
else:
    print(g())
