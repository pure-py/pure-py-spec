# rule: assign
def f() -> int:
    x: int = 5
    x = lambda: x
    return x()

print(type(f()).__name__)
