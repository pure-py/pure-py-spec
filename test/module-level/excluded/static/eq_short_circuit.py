# rule: binop -- == between lists decided at the first element, which Python does and
# PurePy's eq-elems specifies; the operand types are not comparable, so no signature
# applies.
print([1, "a"] == [2, 3])
