# rule: seq
def f() -> int:
    def g() -> int:
        z = 1
        return z
    return g()

z = 5
print(f())
