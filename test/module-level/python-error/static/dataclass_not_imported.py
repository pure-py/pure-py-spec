# rule: class -- class declaration names dataclass, which must be in scope
@dataclass
class P:
    x: int

print(P(1).x)
