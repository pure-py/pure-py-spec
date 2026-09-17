# rule: assign
def f() -> int:
    x = 5
    x = lambda: x
    return x()

print(type(f()).__name__)
