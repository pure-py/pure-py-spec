# rule: var
def f() -> int:
    x: int
    def g() -> int:
        return x
    x = 1
    return g()

print(f())
