def f():
    x = 5
    def x():
        return x  # sibling x (self-recursive), not the outer x
    return x()

print(type(f()).__name__)
