# dynamic-semantic: PurePy is stuck (5 is not a closure), CPython raises.
# Both agree it fails; without types PurePy has no explicit failure mode.
x = 5
y = x(3)
