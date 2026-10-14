# rule: ty-alias
type Opt[T] = T | None

x: Opt[int] = None
y: Opt[int] = 3
print(x)
print(y)
