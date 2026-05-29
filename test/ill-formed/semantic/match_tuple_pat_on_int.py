# Tuple pattern against an int value. Python: sequence pattern requires a
# Sequence, falls through; PurePy: ill-formed by spec (kind mismatch).
v = 5
match v:
    case (a, b):
        print(a, b)
    case _:
        print("nope")
