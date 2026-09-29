# rule: pat-as
def f(v: int) -> str:
    match v:
        case 1 as y:
            return y
        case _:
            return "other"


print(f(1))
