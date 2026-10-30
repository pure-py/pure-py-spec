# rule: var
def f(b: bool) -> int:
    y: int = x
    if b:
        x: int = 1
    return y

print(f(True))
