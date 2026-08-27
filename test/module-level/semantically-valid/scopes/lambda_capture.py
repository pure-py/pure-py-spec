def f(n: int) -> int:
    g = lambda x: x + n
    return g(1)

print(f(10))
