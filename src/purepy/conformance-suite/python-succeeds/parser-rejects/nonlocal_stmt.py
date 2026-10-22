def f() -> int:
    x: int = 5
    def g() -> int:
        nonlocal x
        return x
    return g()

print(f())
