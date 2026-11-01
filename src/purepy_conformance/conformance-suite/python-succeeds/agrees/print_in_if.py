# rule: print
n: int = 3
if n > 2:
    print("big")
else:
    print("small")
match n:
    case 3:
        print(n)
    case _:
        pass
