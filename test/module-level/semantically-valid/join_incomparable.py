# rule: if-else
def f(b: bool) -> int | str:
    x: int | str = 0
    if b:
        x = 1
    else:
        x = "a"
    y: int | str = x
    return y

print(f(True))
print(f(False))
