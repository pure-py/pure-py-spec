# rule: assert-false
def f(b: bool) -> int:
    if b:
        return 1
    assert False
    return 0

print(f(True))
