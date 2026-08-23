# == between a number and a string. Python compares any two operands; PurePy's eq has no
# case for operands of unrelated types, so eval-bin-op is stuck. Statically rejectable
# once the type system lands (#92).
print(1 == "a")
