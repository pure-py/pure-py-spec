# rule: subty-dict
def f(d: dict[str, int | str]) -> dict[str, str | int]:
    return d

print(f({"a": 1}))
