# rule: ty-alias
def make() -> int:
    n: Num = 1
    return n

type Num = int

print(make())
