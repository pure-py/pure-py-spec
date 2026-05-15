def f():
    x = 5
    def x():
        return x  # PurePy: error (x captured and reassigned by def); Python: late binding
    return x()  # Python: returns the function itself

print(type(f()).__name__)
