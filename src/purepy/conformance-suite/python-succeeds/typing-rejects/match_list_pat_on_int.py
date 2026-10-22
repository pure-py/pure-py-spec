# rule: pat-shapes
v: int = 5
match v:
    case [a]:
        print(a)
    case _:
        print("no")
