# rule: ty-alias
type Pair[A, B] = tuple[B, A]

p: Pair[int, str] = ("a", 1)
print(p)
