# rule: return
def f(b: bool) -> int:
    if b:
        assert (False,)[0]
    else:
        return "s"


print(f(False))
