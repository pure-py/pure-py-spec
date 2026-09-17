# rule: subty-class
import a
import b

def f(c: a.C) -> int:
    return c.x

print(f(b.C(1)))  # PurePy: error (b.C is not a.C); Python: runs
