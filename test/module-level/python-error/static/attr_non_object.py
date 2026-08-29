# rule: attr-object -- an attribute reference needs an object of a class type
x = 5
y = x.foo  # PurePy: error (no rule types this); Python: AttributeError
