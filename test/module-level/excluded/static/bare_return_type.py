# rule: return-none -- a bare return requires None to be a subtype of the result type
def f() -> int:
    return

print(f())
