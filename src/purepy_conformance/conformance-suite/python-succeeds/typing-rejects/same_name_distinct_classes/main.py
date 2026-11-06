# judgement: synth, rule: call
import a
import b

def f(c: a.C) -> int:
    return c.x

print(f(b.C(1)))
