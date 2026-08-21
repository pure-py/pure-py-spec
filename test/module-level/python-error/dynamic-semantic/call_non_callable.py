# dynamic-semantic: calling a non-closure. Python raises TypeError; PurePy's
# eval-call-nonfun gives fails TypeError, after evaluating the arguments.
def g():
    print("arg")
    return 3
x = 5
y = x(g())
