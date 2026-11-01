# rule: or
x: bool = False
y: bool = False
z: bool = True
print(x or y or z)
print(x or y or x)
print(z or 1 // 0 == 0 or x)
