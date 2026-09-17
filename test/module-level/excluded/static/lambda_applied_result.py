# rule: syn-call-lambda
x: str = (lambda a: a + 1)(2)  # PurePy: error (body is an int); Python: runs
print(x)
