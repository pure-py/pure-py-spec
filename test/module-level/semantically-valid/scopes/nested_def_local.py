# rule: seq
def f() -> int:
    def g() -> int:
        z: int = 1
        return z
    return g()

z: int = 5
print(f())
