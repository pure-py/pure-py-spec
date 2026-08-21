# rule: var
def foo(b):
    x = 6
    if b:
        x = 3
        y = x + 1
    else:
        y = 0
    return x  # PurePy: error (partially defined); Python: 3 or 6

print(foo(True))
print(foo(False))
