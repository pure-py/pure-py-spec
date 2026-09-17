# rule: assign
def f() -> int:
    x = 5
    x = lambda: x
    return x()  # Python: returns the lambda itself

print(type(f()).__name__)
