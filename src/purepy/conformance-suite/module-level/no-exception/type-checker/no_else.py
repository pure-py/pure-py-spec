# rule: var
def foo(b: bool) -> int:
    x: int
    if b:
        x = 1
    return x

print(foo(True))
