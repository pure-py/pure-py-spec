def f() -> int:
    x = 5
    def x(n: int) -> int:
        if n == 0:
            return 0
        return x(n - 1)  # sibling x (self-recursive), not the outer x
    return x(3)

print(f())
