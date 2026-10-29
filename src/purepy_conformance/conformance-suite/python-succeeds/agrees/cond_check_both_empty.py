# rule: cond
def f(b: bool) -> int:
    xs: list[int] = [] if b else []
    return len(xs)

print(f(True))
