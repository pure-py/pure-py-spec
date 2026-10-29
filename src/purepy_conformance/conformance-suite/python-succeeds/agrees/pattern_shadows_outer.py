# rule: pat-var
def f(v: int) -> int:
    x: int = v

    def g(w: int) -> int:
        match w:
            case x:
                return x

    return g(x)


print(f(3))
