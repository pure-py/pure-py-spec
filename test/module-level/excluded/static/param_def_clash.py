# rule: def-body
def f(g: int) -> int:
    def g() -> int:
        return 1
    return g()

print(f(3))
