# dynamic-semantic: a Boolean assertion that fails. Python raises AssertionError;
# PurePy's eval-assert-false gives fails AssertionError, unlike assert_falsy,
# which is a truthiness case.
assert False
