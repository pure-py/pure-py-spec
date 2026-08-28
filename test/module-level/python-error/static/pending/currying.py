# rule: (not yet caught; needs an arity check)
def f(x: int, y: int) -> int:
    return x + y

f(5)(6)  # PurePy: ill-formed (unsaturated call); Python: TypeError
