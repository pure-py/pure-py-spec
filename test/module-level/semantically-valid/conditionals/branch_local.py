def foo(b: bool) -> int:
    z = 6
    if b:
        x = 3
        y = x + 1
    else:
        y = 0
    return z

print(foo(True))
print(foo(False))
