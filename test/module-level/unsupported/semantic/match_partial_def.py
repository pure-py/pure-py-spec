# rule: match definite assignment -- y assigned in only one arm
v = 1
match v:
    case 1:
        y = 10
    case _:
        pass
print(y)
