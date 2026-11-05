# rule: match
# bug: https://github.com/python/mypy/issues/22202
def f() -> int:
    match False:
        case False:
            return 0


print(f())
