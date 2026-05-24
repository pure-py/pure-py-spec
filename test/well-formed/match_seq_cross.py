# Sequence patterns are bracket-agnostic: list pattern matches tuple
# value, and tuple pattern matches list value.
v_tup = (1, 2)
match v_tup:
    case [a, b]:
        print("list pat matched tuple:", a, b)
    case _:
        print("other")

v_lst = [3, 4]
match v_lst:
    case (c, d):
        print("tuple pat matched list:", c, d)
    case _:
        print("other")
