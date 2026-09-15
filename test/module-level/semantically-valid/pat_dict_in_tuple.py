# rule: pat-tuple -- a tuple type's shapes carry component shapes, a dictionary
# component its dictionary form
def f(t: tuple[dict[str, int], int]) -> int:
    match t:
        case ({"a": n}, 1):
            return n
        case _:
            return 0


print(f(({"a": 1}, 1)))
