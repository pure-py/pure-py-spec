# rule: assert
def f(b: bool) -> int:
    if b:
        return 1
    assert (False,)[0]

print(f(True))
