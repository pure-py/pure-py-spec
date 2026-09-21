# rule: syn-cond
def f(b: bool) -> int | str:
    x: int | str = 1 if b else "a"
    return x


print(f(True))
print(f(False))
