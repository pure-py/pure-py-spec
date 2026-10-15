# rule: match-partial
v: int = 1
y: int
match v:
    case 1:
        y = 10
    case _:
        pass
print(y)
