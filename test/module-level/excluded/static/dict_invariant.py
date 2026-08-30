# rule: subty-refl -- dictionaries are related only by reflexivity
d: dict[str, int] = {"a": 1}
e: dict[str, float] = d  # PurePy: error (dict is invariant); Python: runs
print(e)
