sq = "hello"
nums = [1, 2, 3, 4]
squares = [sq := n*n for n in nums]
print(sq)  # PurePy: ill-formed (walrus operator unsupported); Python: 16
