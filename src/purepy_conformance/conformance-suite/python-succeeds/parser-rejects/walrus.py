sq: str = "hello"
nums: list[int] = [1, 2, 3, 4]
squares = [sq := n*n for n in nums]
print(sq)
