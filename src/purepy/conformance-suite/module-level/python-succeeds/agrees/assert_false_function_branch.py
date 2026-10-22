# rule: assert-false
def f(b: bool) -> int:
    x: int
    if b:
        x = 1
    else:
        assert False
    return x


print(f(True))
