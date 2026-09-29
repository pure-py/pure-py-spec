# rule: if
def f(b: bool) -> int:
    x: int
    if b:
        x = 1
    def g() -> int:
        return x
    x = 2
    return g()

print(f(False))
