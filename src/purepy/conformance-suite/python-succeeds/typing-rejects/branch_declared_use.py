# rule: var
def f(b: bool) -> int:
    if b:
        y: int = 1
    return y

print(f(True))
