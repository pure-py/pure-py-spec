v = 1
match v:
    case 1:
        import sys
        print(sys.argv != "")
    case _:
        print("other")
