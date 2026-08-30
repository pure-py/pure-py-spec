# rule: pat-shapes -- a case must match some shape the earlier cases leave
x = None
match x:
    case None:
        print("none")
    case _:
        print("other")
