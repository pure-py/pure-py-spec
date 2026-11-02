v: int = 3
match v:
    case y if y > 2:
        print("big")
    case _:
        print("small")
