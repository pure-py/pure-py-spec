# judgement: synth, rule: var
x: int = 42
y: str
match x:
    case 42:
        y = "yes"
print(y)
