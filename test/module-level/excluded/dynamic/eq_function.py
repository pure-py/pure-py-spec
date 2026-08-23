# == between two functions. Python compares closures by identity;
# PurePy's eq has no case for closures, so eval-bin-op is stuck. Statically
# rejectable once the type system lands (#92).
def f(x):
    return x
print(f == f)
