# rule: syn-dict-comp
d = {k: 1 for k in ["a", "b"]}
n: str = d["a"]
print(n)
