# static-semantic/pending: tuple pattern against an int value. Python requires a
# Sequence so the case falls through; PurePy has no matching rule. Statically
# rejectable once the type system lands (#92).
v = 5
match v:
    case (a, b):
        print(a, b)
    case _:
        print("nope")
