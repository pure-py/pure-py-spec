# rule: type-alias
type Nested = int | list[Nested]

v: Nested = 3
print(v)
