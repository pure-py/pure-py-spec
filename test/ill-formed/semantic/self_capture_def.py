def f():
    x = 5
    def x():
        return x  # PurePy: error (x captured and reassigned by def); Python: late binding
    return x()  # Python: returns the function itself; pure semantics: returns 5

print(type(f()).__name__)
