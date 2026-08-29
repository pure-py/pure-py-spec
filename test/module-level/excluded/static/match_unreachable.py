# rule: cases-cons -- a case must not be subsumed by an earlier one
v = (1, 2)
match v:
    case (a, b):
        print("seq", a, b)
    case (1, 2):  # PurePy: error (subsumed by previous); Python: silently unreachable
        print("lit")
