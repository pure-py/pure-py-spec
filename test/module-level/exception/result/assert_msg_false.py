# rule: eval-assert-msg-false
def f() -> int:
    assert False, "boom"


f()
