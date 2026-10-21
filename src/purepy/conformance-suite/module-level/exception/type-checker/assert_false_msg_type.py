# rule: assert-false-msg
def f(b: bool) -> int:
    if b:
        return 1
    assert False, 42


print(f(False))
