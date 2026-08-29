# rule: assign-unannot -- a lambda has no type of its own, so it cannot be assigned unannotated
x = lambda a: a + 10  # PurePy: error (no type for the lambda); Python: runs
print(x(5))
