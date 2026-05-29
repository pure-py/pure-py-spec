# PurePy: imports must be at module top level; Python: accepts imports inside if branches.
if True:
    import sys
print(sys.platform != "")
