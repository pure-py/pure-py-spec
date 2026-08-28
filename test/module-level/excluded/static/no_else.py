# rule: var
def foo(b: bool) -> int:
    x = 0
    if b:
        x = 1
    return x

print(foo(True))
print(foo(False))
