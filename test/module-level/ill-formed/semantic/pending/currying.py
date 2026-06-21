# rule: (not yet caught; needs an arity check)
def f(x, y):
    return x + y

f(5)(6)  # PurePy: ill-formed (unsaturated call); Python: TypeError
