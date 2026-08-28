# rule: call -- a call supplies every parameter; Python raises TypeError
def f(x: int, y: int) -> int:
    return x + y

f(5)(6)
