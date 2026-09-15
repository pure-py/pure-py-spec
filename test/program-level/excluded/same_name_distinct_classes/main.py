# rule: subty-class -- a class is identified by its qualified name, so two modules' classes called C are distinct types
import a
import b

def f(c: a.C) -> int:
    return c.x

print(f(b.C(1)))  # PurePy: error (b.C is not a.C); Python: runs
