# rule: def-body
def f() -> int:
    match 1.5:
        case 1.5:
            return 1


print(f())
