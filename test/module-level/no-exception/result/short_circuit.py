# rule: eval-and-false
print(False and 1 // 0 == 0)
print(True or 1 // 0 == 0)
print(1 if True else 1 // 0)
