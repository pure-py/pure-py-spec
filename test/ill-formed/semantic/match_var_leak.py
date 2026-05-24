# rule: match-partial (var leak — x not definitely assigned after partial match)
v = (1, 2)
match v:
    case (x, y):
        print(x, y)
print(x)  # PurePy: error (x not definitely assigned); Python: 1
