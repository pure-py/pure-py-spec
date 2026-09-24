# rule: module
def f(b: bool) -> int:
    if b:
        y: int = 1
    else:
        y: int = 2
    return y

print(f(True))
