# rule: seq -- a variable assigned in a nested definition is local to it, so the outer definition does not capture it
def f() -> int:
    def g() -> int:
        z = 1
        return z
    return g()

z = 5
print(f())
