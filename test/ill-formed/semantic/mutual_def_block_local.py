b = True

if b:
    def f():
        return g()
    def g():
        return "g via mutual block"
else:
    def f():
        return "f only"

print(g())  # PurePy: error (g not definitely assigned); Python: ok when b is True
