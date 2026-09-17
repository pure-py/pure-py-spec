# rule: eval-if
def classify(n: int) -> str:
    if n == 0:
        return "zero"
    elif n == 1:
        return "one"
    else:
        return "many"
print(classify(1))
