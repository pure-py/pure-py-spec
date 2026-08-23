# rule: eval-pat-tuple-no -- a tuple pattern against a non-sequence gives no-match,
# so the next case runs, as in Python.
v = 5
match v:
    case (a, b):
        print(a, b)
    case _:
        print("nope")
