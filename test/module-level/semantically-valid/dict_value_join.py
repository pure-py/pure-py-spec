# rule: syn-dict -- values join at their base types
d = {"a": 1, "b": 2}
n: int = d["a"]
print(n)
