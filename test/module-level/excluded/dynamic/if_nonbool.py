# a non-boolean if condition. Python runs via truthiness;
# PurePy's eval-if is stuck (5 is not True/False). Statically rejectable once the
# type system lands (#92).
if 5:
    print("yes")
