# dynamic-semantic: == between a bool and an int. Python identifies True with 1;
# PurePy's eq relates booleans only to booleans, so eval-bin-op is stuck. A
# mypy-compatible type system cannot reject this, since bool is a subtype of int.
print(True == 1)
