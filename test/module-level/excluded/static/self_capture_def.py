# rule: def
def f() -> int:
    x: int = 5
    def x(n: int) -> int:
        if n == 0:
            return 0
        return x(n - 1)
    return x(3)

print(f())
