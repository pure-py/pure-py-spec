# rule: seq
def f(b: bool) -> int:
    if b:
        return 1
    else:
        return 2
    print("never")

print(f(True))
