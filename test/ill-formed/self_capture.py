def f():
    x = 5
    x = lambda: x  # PurePy: error (x captured and reassigned in same statement); Python: late binding
    return x()  # Python: returns the lambda itself; pure semantics: returns 5

print(type(f()).__name__)
