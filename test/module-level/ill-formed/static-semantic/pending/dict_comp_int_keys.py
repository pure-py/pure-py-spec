# Integer keys in a dict comprehension. Python: accepts; PurePy: ill-formed by
# spec (see §Unsupported Python features), since dict keys must be strings.
xs = [1, 2, 3]
print({x: x + 1 for x in xs})
