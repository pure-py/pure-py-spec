# rule: assert-false-msg
def f(b: bool) -> int:
    if b:
        return 1
    assert False, "b is false"

print(f(True))
