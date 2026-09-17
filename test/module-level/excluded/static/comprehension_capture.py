# rule: list-comp
powers = [lambda x: x**i for i in [1, 2, 3]]
print(powers[2](2))
