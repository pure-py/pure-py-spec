# rule: match-partial
def f(s: str) -> int:
    match s:
        case "a":
            return 1
        case "b":
            return 2


print(f("a"))
