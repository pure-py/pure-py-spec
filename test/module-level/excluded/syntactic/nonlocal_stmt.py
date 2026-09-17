def f() -> int:
    x = 5
    def g() -> int:
        nonlocal x
        return x
    return g()

print(f())
