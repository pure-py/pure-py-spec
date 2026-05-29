# String literal pattern against an int value. Python: comparison is False,
# falls through; PurePy: ill-formed by spec (kind mismatch).
v = 5
match v:
    case "x":
        print("yes")
    case _:
        print("no")
