# judgement: resolve-type, rule: ty-dict
def f() -> int:
    str: int = 5
    d: dict[str, int] = {"a": str}
    return d["a"]


print(f())
