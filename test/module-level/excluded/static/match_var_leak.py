# rule: match-partial (var leak — x not definitely assigned after partial match)
v: tuple[int, int] = (1, 2)
match v:
    case (x, 2):
        print(x, 2)
print(x)  # PurePy: error (x not definitely assigned); Python: 1
