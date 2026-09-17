# rule: attr-object
x = 5
y = x.foo  # PurePy: error (no rule types this); Python: AttributeError
