def f(x: int) -> int:
    a = x
    x = 5
    b = x
    return a + b

print(f(10))
