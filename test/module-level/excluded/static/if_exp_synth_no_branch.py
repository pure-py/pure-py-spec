# rule: cond-syn
b: bool = True
print(([] if b else []) + [1])
