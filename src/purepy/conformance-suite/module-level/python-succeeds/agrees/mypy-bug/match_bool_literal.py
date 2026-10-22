# rule: match
def f() -> int:
    match False:
        case False:
            return 0


print(f())
