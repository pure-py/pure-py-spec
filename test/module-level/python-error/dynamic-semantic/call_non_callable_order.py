# dynamic-semantic: the argument is evaluated before the call fails. Python prints
# then raises TypeError; PurePy's eval-call-nonfun requires the arguments to
# succeed before the failure arises.
def g():
    print("arg")
    return 1
x = 5
y = x(g())
