# PurePy: imports must be at module top level; Python: accepts intra-function imports.
def f():
    import sys
    return sys.platform

print(f() != "")
