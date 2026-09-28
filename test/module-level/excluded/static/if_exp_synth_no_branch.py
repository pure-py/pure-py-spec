# rule: syn-cond
b: bool = True
print(([] if b else []) + [1])
