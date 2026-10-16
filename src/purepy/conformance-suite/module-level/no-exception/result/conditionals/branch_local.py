def foo(b: bool) -> int:
    z: int = 6
    x: int
    y: int
    if b:
        x = 3
        y = x + 1
    else:
        y = 0
    return z

print(foo(True))
print(foo(False))
