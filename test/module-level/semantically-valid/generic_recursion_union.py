def f[T](x: T | None, n: int) -> int:
    if n == 0:
        return 0
    return f(x, n - 1)


print(f(1, 2))
