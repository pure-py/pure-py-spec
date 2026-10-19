Write PurePy v0.22.3, a statically checked functional subset of Python 3.12.
Only the following differences from Python matter here.

Excluded:
- No for/while statements, generator expressions, yield, async, try/raise, with,
  global/nonlocal, assignment expressions, or mutation of objects/containers.
- No rebinding an assigned variable, augmented assignment, destructuring
  assignment, slicing, sets, f-strings, identity tests, or chained comparisons.
- No default/variadic/keyword-only parameters. Call functions positionally.
  Keyword arguments are supported only for dataclass constructors.
- No built-in container/string methods, conversion calls, or arbitrary libraries.
  In particular, sum, min, max, abs, sorted, enumerate, zip and math are unavailable.

Required:
- Annotate every function parameter and return type. Declare every local variable
  with a type annotation before or when assigning it, and assign it only once.
  Comprehension and pattern variables are bound by their construct.
- Conditions must be bool, not implicit truth tests of integers or containers.
- Use recursion, list/dict comprehensions, helpers and fresh values instead of
  loops and mutation. Avoid linear recursion depth on large inputs.
- Use int, float, bool, str, None, object, list[T], dict[str, T], fixed-length
  tuple[...] and unions as types. Import Callable, Literal, Never or Sized from
  typing when needed. A class must be a supported @dataclass with typed fields
  and no methods or field defaults.
- Imports must precede other statements. Predefined runtime calls are len(x),
  range(start, stop), round(float_value), print(x) and sys.exit(int_value).
  range(n), conversion constructors such as int(x), and extra call arguments
  are unavailable. Prefer no I/O for these tasks.

Replace a loop that appends squared values with:

```python
def squares(xs: list[int]) -> list[int]:
    return [x * x for x in xs]
```

Replace an updating accumulator with a recursive helper:

```python
def total_from(xs: list[int], i: int) -> int:
    if i == len(xs):
        return 0
    return xs[i] + total_from(xs, i + 1)

def total(xs: list[int]) -> int:
    return total_from(xs, 0)
```

Declare fresh names rather than updating an existing one:

```python
def advance(x: int) -> int:
    next_x: int = x + 1
    return next_x
```
