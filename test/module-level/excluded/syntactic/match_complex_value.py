v = 1
match v:
    case 1 + 2j:  # PurePy: prohibited (complex literal pattern); Python: runs
        pass
