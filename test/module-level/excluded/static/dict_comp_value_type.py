# rule: syn-dict-comp
d: dict[str, int] = {k: 1 for k in ["a", "b"]}
n: str = d["a"]
print(n)
