# tuple pattern against a list value. Python matches; PurePy's eval-pat-tuple-no does
# not fire on a sequence of the other kind, so the match has no derivation and the run
# has no result. Statically rejectable once the type system arrives (#92).
v = [1, 2]
match v:
    case (a, b):
        print(a, b)
    case _:
        print("other")
