from shapes import Derived

d = Derived(1, 2)
print(d.x)
print(d.y)

def total(v: Derived) -> int:
    match v:
        case Derived(x, y):
            return x + y

print(total(d))
