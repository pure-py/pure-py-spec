# rule: list-comp -- a lambda in the body may not capture a generator variable
powers = [lambda x: x**i for i in range(10)]
print(powers[3](2))  # PurePy: error; Python: 512, every lambda sees i = 9
