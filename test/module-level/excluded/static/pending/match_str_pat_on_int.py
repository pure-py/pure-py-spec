# string literal pattern against an int value. Python's comparison is False so the case
# falls through; PurePy has no matching rule. Statically rejectable once the type system
# lands (#92).
v = 5
match v:
    case "x":
        print("yes")
    case _:
        print("no")
