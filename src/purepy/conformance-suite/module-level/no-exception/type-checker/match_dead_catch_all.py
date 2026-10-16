# rule: pat-shapes
x: None = None
match x:
    case None:
        print("none")
    case _:
        print("other")
