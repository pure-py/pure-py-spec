# rule: if / eval-if -- elif chain (>=3 branches; selects the elif)
def classify(n):
    if n == 0:
        return "zero"
    elif n == 1:
        return "one"
    else:
        return "many"
print(classify(1))
