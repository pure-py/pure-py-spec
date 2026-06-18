# rule: pat-list (reachability)
v = (1, 2)
match v:
    case (a, b):
        print("seq", a, b)
    case (1, 2):  # PurePy: error (subsumed by previous); Python: silently unreachable
        print("lit")
