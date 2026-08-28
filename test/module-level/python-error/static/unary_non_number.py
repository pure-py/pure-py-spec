# rule: unop -- negation of a non-number. Python raises TypeError; PurePy has no
# signature for this operand.
print(-"a")
