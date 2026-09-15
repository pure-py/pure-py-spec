# rule: list-comp -- a lambda in the body may not capture a generator variable
powers = [lambda x: x**i for i in [1, 2, 3]]
print(powers[2](2))  # PurePy: error; Python: 8, every lambda sees i = 3
