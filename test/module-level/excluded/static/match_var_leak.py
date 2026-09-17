# rule: match-partial
v: tuple[int, int] = (1, 2)
match v:
    case (x, 2):
        print(x)
        print(2)
print(x)  # PurePy: error (x not definitely assigned); Python: 1
