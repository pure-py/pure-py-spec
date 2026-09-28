# rule: match
def f(v: None) -> int:
    match v:
        case None:
            return 0


print(f(None))
