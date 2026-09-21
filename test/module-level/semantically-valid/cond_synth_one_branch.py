# rule: syn-cond
def f(b: bool) -> int:
    xs: list[int] = [] if b else [1]
    return len(xs)


print(f(True))
print(f(False))
