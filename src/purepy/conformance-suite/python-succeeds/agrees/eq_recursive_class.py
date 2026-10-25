# rule: binop
from dataclasses import dataclass

type A = D | None


@dataclass
class C:
    x: A


@dataclass
class D:
    y: C


print(C(D(C(None))) == C(D(C(None))))
