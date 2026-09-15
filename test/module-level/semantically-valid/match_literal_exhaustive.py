# rule: match -- a literal-typed scrutinee is exhausted by covering its literals
x = 42
match x:
    case 42:
        y = "yes"
print(y)
