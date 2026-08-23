# a non-boolean assert condition. Python raises via truthiness;
# PurePy's eval-assert is stuck (0 is not True). Statically rejectable once the
# type system lands (#92).
assert 0
