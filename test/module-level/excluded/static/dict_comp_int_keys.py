# rule: syn-dict-comp -- keys must be strings
xs = [1, 2, 3]
print({x: x + 1 for x in xs})
