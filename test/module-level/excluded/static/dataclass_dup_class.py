# rule: top-seq -- a second declaration cannot take an existing class's name

@dataclass
class C:
    pass

@dataclass
class C:  # PurePy: error (name already bound); Python: shadows the first
    pass

print("ok")
