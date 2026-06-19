# Literal int pattern against a list value. Python: comparison is False, falls
# through; PurePy: ill-formed by spec (kind mismatch).
v = [1, 2]
match v:
    case 1:
        print("yes")
    case _:
        print("no")
