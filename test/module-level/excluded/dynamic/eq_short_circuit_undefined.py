# == between lists whose first elements are equal, so eq-elems reaches "a" against 3, for
# which eq has no case: eval-binop is stuck. Python compares any two operands and prints
# False. Statically rejectable once the type system lands (#92).
print([1, "a"] == [1, 3])
