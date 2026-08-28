# rule: binop -- == between lists whose first elements are equal, so eq-elems would
# reach "a" against 3, for which eq has no case; the operand types are not comparable, so
# no signature applies.
print([1, "a"] == [1, 3])
