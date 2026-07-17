# rule: if / definite assignment -- if/elif with no else does not definitely assign y
x = 1
if x == 0:
    y = 1
elif x == 1:
    y = 2
print(y)
