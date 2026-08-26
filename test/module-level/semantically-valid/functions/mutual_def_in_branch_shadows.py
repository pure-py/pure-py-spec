b = True

def g():
    return 0

if b:
    def f():
        return g()  # sibling g, bound simultaneously, not the outer g
    def g():
        return 1
    print(f())
else:
    print(g())
