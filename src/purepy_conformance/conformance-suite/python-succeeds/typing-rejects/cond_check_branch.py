# rule: cond
def f(b: bool) -> int:
    xs: list[int] = [] if b else ["a"]
    return len(xs)

print(f(True))
