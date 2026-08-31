# rule: syn-cond -- a conditional expression synthesises the join of its branches
def f(b: bool) -> int | str:
    x = 1 if b else "a"
    return x


print(f(True))
print(f(False))
