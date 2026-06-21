# List pattern matching a tuple value. Python: matches; PurePy: ill-formed by spec
# (see §Unsupported Python features).
v = (1, 2)
match v:
    case [a, b]:
        print(a, b)
    case _:
        print("other")
