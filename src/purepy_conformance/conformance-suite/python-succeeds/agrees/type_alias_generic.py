# rule: ty-alias
type Pair[T] = tuple[T, T]

p: Pair[int] = (1, 2)
match p:
    case (a, b):
        print(a + b)
