powers = [(lambda i: (lambda x: x**i))(i) for i in range(10)]
print(powers[3](2))
