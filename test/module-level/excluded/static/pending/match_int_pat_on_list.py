# literal int pattern against a list value. Python's
# comparison is False so the case falls through; PurePy has no matching rule.
# Statically rejectable once the type system lands (#92).
v = [1, 2]
match v:
    case 1:
        print("yes")
    case _:
        print("no")
