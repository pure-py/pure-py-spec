def deco(c: object) -> object:
    return c

@deco
class C:
    pass
