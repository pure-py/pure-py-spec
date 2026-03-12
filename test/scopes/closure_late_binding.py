def f():
    x = 6
    def g():
        return x
    x = 7
    return g

print(f()())
