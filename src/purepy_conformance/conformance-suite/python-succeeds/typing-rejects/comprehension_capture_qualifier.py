# rule: qual-generator
print([j for i in [1, 2] for j in (lambda: [i])()])
