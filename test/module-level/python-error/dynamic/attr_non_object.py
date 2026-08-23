# attribute access on a non-object. Python raises
# AttributeError; PurePy's eval-attr-nonobj gives fails AttributeError.
x = 5
y = x.foo
