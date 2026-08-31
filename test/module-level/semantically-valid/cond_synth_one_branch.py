# rule: syn-cond -- the branch that does not synthesise checks against the join
def f(b: bool) -> int:
    xs = [] if b else [1]
    return len(xs)


print(f(True))
print(f(False))
