# rule: assign-unannot
x = lambda a: a + 10  # PurePy: error (no type for the lambda); Python: runs
print(x(5))
