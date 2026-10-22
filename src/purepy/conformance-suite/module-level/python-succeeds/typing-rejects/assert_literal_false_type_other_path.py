# rule: def-body
def f(b: bool) -> int:
    if b:
        pass
    else:
        assert (False,)[0]


print(f(True))
