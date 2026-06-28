# pending static rejection (blocked on the mypy type system): a non-boolean if
# condition. CPython runs via truthiness; PurePy's eval-if is stuck (5 is not
# True/False), so PurePy must reject this once types are available.
if 5:
    print("yes")
