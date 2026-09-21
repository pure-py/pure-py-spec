# rule: assign
def f(b: bool) -> int:
    x: int
    if b:
        x = 1
    x = 2
    return x

print(f(True))
