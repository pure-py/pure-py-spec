# rule: lambda -- a lambda checks only against a callable type
x: int = lambda y: y
print(x(1))
