# integer keys in a dict comprehension. Python accepts;
# PurePy's eval-dict-comp requires keys to evaluate to strings. Statically
# rejectable once the type system lands (#92).
xs = [1, 2, 3]
print({x: x + 1 for x in xs})
