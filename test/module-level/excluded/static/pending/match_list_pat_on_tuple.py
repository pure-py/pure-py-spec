# list pattern against a tuple value. Python matches;
# PurePy's sub-list-list admits only lists, so a later case runs and the two
# languages differ. Statically rejectable once unions are restricted (#151).
v = (1, 2)
match v:
    case [a, b]:
        print(a, b)
    case _:
        print("other")
