# dynamic-semantic: calling a non-closure. Python raises TypeError; PurePy's
# eval-call-nonfun gives fails TypeError.
x = 5
y = x(3)
