# rule: syn-cond
def f(b: bool) -> int | str:
    x = 1 if b else "a"
    return x


print(f(True))
print(f(False))
