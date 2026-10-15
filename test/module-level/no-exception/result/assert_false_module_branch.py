# rule: assert-false
def f() -> bool:
    return True


if f():
    x: int = 1
else:
    assert False
print(x)
