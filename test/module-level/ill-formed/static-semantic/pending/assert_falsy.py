# pending static rejection (blocked on the mypy type system): a non-boolean assert
# condition. PurePy's eval-assert succeeds on 0 (0 != False) but CPython raises -- a
# real divergence, so PurePy must reject this once types are available.
assert 0
