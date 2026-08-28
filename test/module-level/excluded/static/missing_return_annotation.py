# rule: def -- every parameter and return carries an annotation
def f(n: int):  # PurePy: error (no return annotation); Python: infers nothing
    return n + 1

print(f(1))
