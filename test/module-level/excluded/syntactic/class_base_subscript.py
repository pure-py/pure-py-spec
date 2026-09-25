from dataclasses import dataclass


@dataclass
class Base:
    value: int


bases = (Base,)


@dataclass
class Derived(bases[0]):
    pass


print(Derived(1))
