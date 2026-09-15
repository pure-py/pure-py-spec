# rule: syn-dict-comp -- value type comes from the body
d = {k: 1 for k in ["a", "b"]}
n: str = d["a"]
print(n)
