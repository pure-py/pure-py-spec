# rule: binop -- == between a bool and an int. Python identifies True with 1;
# PurePy does not treat bool as a subtype of int, so no signature applies.
print(True == 1)
