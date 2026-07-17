# rule: attr-module -- a predefined module exposes only its declared members
# (PurePy's math has none; Python's has pi).
import math
x = math.pi
print(x)
