# rule: qualified
import pkg.sub
p: pkg.sub.C = pkg.sub.C(5)
match p:
    case pkg.sub.C(x):
        print(x)
