# rule: call-lambda -- the call gives the type of the body
x: str = (lambda a: a + 1)(2)  # PurePy: error (body is an int); Python: runs
print(x)
