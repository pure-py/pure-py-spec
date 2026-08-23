# integer dict keys. Python accepts; PurePy's eval-dict requires keys to evaluate to
# strings. Statically rejectable once the type system lands (#92).
d = {1: 2, 3: 4}
print(len(d))
