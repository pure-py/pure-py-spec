# dynamic-semantic: == between a bool and an int. Python identifies True with 1;
# PurePy's eq relates booleans only to booleans, so eval-bin-op is stuck.
# Statically rejectable once the type system lands (#92), which will not treat
# bool as a subtype of int.
print(True == 1)
