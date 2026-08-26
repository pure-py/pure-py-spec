# attribute access on a non-object. Python raises AttributeError; PurePy has no
# rule for an attribute reference on a number, so evaluation is stuck.
x = 5
y = x.foo
