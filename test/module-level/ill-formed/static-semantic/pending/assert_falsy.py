# pending static rejection (blocked on the mypy type system): a non-boolean assert
# condition. Python raises via truthiness; PurePy's eval-assert is stuck (0 is not
# True), so PurePy must reject this once types are available.
assert 0
