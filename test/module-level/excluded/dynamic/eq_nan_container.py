# == between lists holding nan. Python compares elements by
# identity before equality, so this is True; PurePy's eq recurses to eq(nan, nan),
# which has no case, so eval-bin-op is stuck. No static check can rule this out,
# since nan is a value (#153, #162).
x = 1e400 - 1e400
print([x] == [x])
