# rule: ty-alias
type Pair[A, B] = tuple[B, A]

p: Pair[int, str] = (1, "a")
print(p)
