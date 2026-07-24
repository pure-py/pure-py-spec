def f():
    x = 5
    def g():
        nonlocal x
        return x
    return g()

print(f())
