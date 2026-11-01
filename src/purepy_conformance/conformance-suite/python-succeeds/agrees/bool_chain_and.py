# rule: and
x: bool = True
y: bool = True
z: bool = False
print(x and y and x)
print(x and y and z)
print(z and 1 // 0 == 0 and x)
