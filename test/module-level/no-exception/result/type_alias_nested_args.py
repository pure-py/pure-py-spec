# rule: ty-alias
type Pair[T] = tuple[T, T]

p: Pair[Pair[int]] = ((1, 2), (3, 4))
print(p)
