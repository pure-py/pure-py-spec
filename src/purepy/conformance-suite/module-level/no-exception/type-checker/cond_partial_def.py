# rule: var
def foo(b: bool) -> int:
    x: int
    y: int
    if b:
        x = 3
        y = x + 1
    else:
        y = 0
    return x

print(foo(True))
