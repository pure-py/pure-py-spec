def last[T](x: T, n: int) -> T:
    return x if n == 0 else last(x, n - 1)


def dup[T](x: T) -> tuple[T, T]:
    y: T = x
    return (y, x)


print(last("a", 3))
print(dup(1))
