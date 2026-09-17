# rule: if-else
def f(b: bool) -> int | str:
    if b:
        x = 1
    else:
        x = "a"
    return x

print(f(True))
print(f(False))
