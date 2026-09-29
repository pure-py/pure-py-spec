# rule: ty-alias
type Num = int
type Pair = tuple[Num, Num]

p: Pair = (1, 2)
match p:
    case (a, b):
        print(a + b)
