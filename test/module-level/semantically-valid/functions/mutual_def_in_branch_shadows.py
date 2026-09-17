b = True

def g() -> int:
    return 0

if b:
    def f() -> int:
        return g()
    def g() -> int:
        return 1
    print(f())
else:
    print(g())
