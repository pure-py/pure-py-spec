# rule: pat-constr
r: range = range(0, 3)
match r:
    case range(start=0, stop=3):
        print("three")
    case _:
        print("other")
