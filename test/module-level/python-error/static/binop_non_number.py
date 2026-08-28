# rule: binop -- arithmetic on a non-number. Python raises TypeError; PurePy has no
# signature for these operands.
print(1 + "a")
