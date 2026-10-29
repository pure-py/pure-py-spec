# rule: syn-dict-comp
print({k: (lambda: k)() for k in ["a"]})
