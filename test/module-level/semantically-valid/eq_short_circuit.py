# == between lists decided at the first element: eq-elems stops there, so the undefined
# comparison of "a" with 3 is never reached. Python agrees.
print([1, "a"] == [2, 3])
