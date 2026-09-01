# rule: split-key -- a key the shape does not bind splits it, leaving the dictionaries
# that lack the key
d = {"a": 1}
match d:
    case {"a": x, "c": y}:
        print(x)
        print(y)
    case _:
        print("no c")
