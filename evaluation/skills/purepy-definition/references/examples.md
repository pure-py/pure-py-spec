# Examples for the Pinned Core

Positive snippets below were accepted independently by the reference module
checker at `68486f84cf80cbc6a4a954dc5d3953951e37b9e3` and exercised under
CPython 3.12. They illustrate language boundaries, not benchmark solutions.

## Single assignment across branches

Declare the name once, then assign it on each mutually exclusive path.

```python
def absolute_value(n: int) -> int:
    result: int
    if n < 0:
        result = -n
    else:
        result = n
    return result
```

## Comprehensions and range

`for` inside a comprehension is allowed. `for` as a statement is excluded.

```python
def positive_squares(xs: list[int]) -> list[int]:
    return [x * x for x in xs if x > 0]

def reverse_text(s: str) -> str:
    def build(i: int) -> str:
        if i < 0:
            return ""
        return s[i] + build(i - 1)
    return build(len(s) - 1)

def indices(n: int) -> list[int]:
    return [i for i in range(0, n)]
```

## Accumulation without mutation or unsupported builtins

Replace loop accumulation and `sum(xs)` with a typed recursive helper.
Indexing avoids unsupported slicing. CPython recursion limits still apply.

```python
def total(xs: list[int]) -> int:
    def accumulate(i: int, acc: int) -> int:
        if i == len(xs):
            return acc
        return accumulate(i + 1, acc + xs[i])
    return accumulate(0, 0)
```

## Contextual lambda typing

```python
from typing import Callable

def apply_twice(f: Callable[[int], int], n: int) -> int:
    return f(f(n))

def plus_two(n: int) -> int:
    return apply_twice(lambda x: x + 1, n)
```

## Dataclasses and complete constructor patterns

Use the bare decorator and include every field in the pattern.

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

def norm_squared(p: Point) -> int:
    match p:
        case Point(x, y):
            return x * x + y * y
```

## String-keyed dictionaries

```python
def bump_values(values: dict[str, int]) -> dict[str, int]:
    return {key: values[key] + 1 for key in values}
```

## Counterexamples

Each row is a separate candidate; the official checker rejected all rows in
the creation-time validation. The stage column identifies the observed check.

| Candidate | Stage | Reason and rewrite |
| --- | --- | --- |
| `x = 1` at module level | Static | Undeclared assignment; use `x: int = 1` |
| `x: int = 1` followed by `x = 2` | Static | Reassignment; introduce a fresh name |
| `if xs:` for `xs: list[int]` | Static | Condition is not `bool`; use `len(xs) > 0` |
| `return xs[1:]` | Syntax | Slicing is not supported; use indices/comprehension |
| `xs.append(1)` | Static | Built-in value attribute is unavailable; build a new list |
| `return sum(xs)` | Static | `sum` is absent from the predefined environment; use a helper |
| `[i for i in range(n)]` | Static | Missing the `start` field; use `range(0, n)` |
| `@dataclass(frozen=True)` | Syntax | Decorator options are excluded; use `@dataclass` |
| `for x in xs: print(x)` | Syntax | Loop statement is excluded |
| `return a is None` | Syntax | Identity operator is not supported; use an appropriate `match` |
| `[lambda x: x + i for i in range(0, 3)]` with a compatible callable-list context | Static | Lambda captures a comprehension generator variable |
| `int("1")` | Static | Annotation-only predefined name used as a value |
| `print(1, 2)` | Static | The predefined `print` takes one argument |

## A static check does not prove correctness

```python
def first(xs: list[int]) -> int:
    return xs[0]
```

This is statically accepted, returns the first element for a nonempty list,
and raises `IndexError` for `[]`. Whether that satisfies a task depends on the
specified input domain. Also check dynamic exclusions independently when a
program manipulates `object` values or NaNs.
