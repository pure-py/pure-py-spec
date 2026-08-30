# PurePy: imports must be at module top level; Python: accepts intra-function imports.
def f() -> list[str]:
    import sys
    return sys.argv

print(f() != "")
