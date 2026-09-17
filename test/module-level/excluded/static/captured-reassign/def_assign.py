# rule: seq
def f() -> int:
    x = 5
    def g() -> int:
        return x
    x = 6
    return x + g()

print(f())
