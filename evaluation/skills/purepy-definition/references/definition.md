# PurePy Core v0.19.0

Specification and reference checker revision:
`68486f84cf80cbc6a4a954dc5d3953951e37b9e3`.
Python runtime for this revision: 3.12.

## Meaning and compatibility

PurePy is a functional subset of Python with a static type system, restrictions
on binding and mutation, and a partial operational semantics. Well-formed
programs are valid Python. Whenever PurePy defines a result for a run, that
result agrees with Python. Well-formedness does not guarantee termination,
absence of runtime errors, or correctness for a task.

Names have lexical scope; each assigned variable denotes a fixed value.
Containers and object fields cannot be mutated by PurePy code. `print` is an
explicitly supported output operation. The specification's purity claim allows
this output; it does not prohibit every observable effect. `sys.argv` is also a
specified input, so reproducibility is understood for the same program inputs.

## Bindings and scope

- Declare ordinary variables with `x: T`, optionally initialized as `x: T = e`.
  A later `x = e` is permitted only after a declaration and only where `x` is
  definitely unassigned. Parameters, imports, function definitions, patterns,
  and comprehension generators introduce their own bindings.
- Assign a variable at most once along any execution path. Assignment neither
  creates an undeclared ordinary variable nor updates an existing value.
  Declare once before branches if both branches assign the same variable.
- Read a variable only where every path reaching the read has assigned it.
  A path that returns before the read does not require an assignment.
  A partially assigned variable cannot be completed by an unconditional
  assignment after the branches.
- A module, function, lambda, or comprehension is a scope. A scope cannot
  declare the same name twice, including redeclaring a parameter or imported
  name. `if` and `match` do not introduce block scopes. Inner scopes may shadow
  enclosing names; the local declaration hides the enclosing binding throughout
  that scope, including before the declaration.
- Closures capture only definitely assigned outer bindings, except that
  contiguous function definitions form a mutual recursion region. A lambda
  in a comprehension must not capture its generator variables, including in
  later qualifiers: Python would expose the rebinding of those variables.
- Assignment targets are simple names. Exclude item/attribute assignment,
  augmented assignment, chained/destructuring assignment, `del`, `global`,
  `nonlocal`, and `:=`.

## Functions and types

- Annotate every `def` parameter and return type. Use ordinary positional
  parameters. Exclude defaults, positional-only and keyword-only parameters,
  `*args`, `**kwargs`, and function decorators.
- Calls supply the declared arity. Ordinary function calls use positional
  arguments; constructor calls may use positional arguments followed by field
  keywords, covering every field exactly once. Argument unpacking is excluded.
- A non-`None` return type requires every path to return an explicit compatible
  value. This includes `T | None`: write `return None` for that branch. Bare
  `return` and implicit fallthrough apply only to return type `None`.
- A call whose declared return type is `None` is used as a statement, not as
  an expression to assign, return, or embed.
- Recursion and nested functions are allowed. Mutually recursive functions must
  be contiguous `def` statements; an intervening statement ends the region.
  Statements after a definite return are rejected as unreachable.
- Lambdas use Python's unannotated parameter syntax. Supply an expected
  `Callable` type through the surrounding context, such as an annotated variable
  or function parameter. An immediately applied lambda can infer its parameter
  types from the arguments.
- Supported type forms: `object`, `Never`, `None`, `bool`, `int`, `float`, `str`,
  `Sized`, `list[T]`, fixed-length `tuple[T1, ..., Tn]`, `tuple[()]`,
  `dict[str, T]`, `Callable[[T1, ..., Tn], R]`, `Literal[value]`, `T | U`,
  declared dataclass types, type aliases, and type parameters.
- Use Python 3.12 syntax for generic definitions and aliases, for example
  `def identity[T](x: T) -> T` and `type Pair[T] = tuple[T, T]`.
  Type parameter bounds, constraints, `ParamSpec`, and `TypeVarTuple` are excluded.
  `Any`, `Optional`, `Union`, `typing.List`, ellipsis tuple types, and quoted
  annotation strings are outside this type grammar.
- `int` is a subtype of `float`. `bool` is separate from numeric types.
  Lists, dictionaries, and dataclass type arguments are invariant; fixed tuples
  are covariant. Callable parameters are contravariant and results covariant.
  Empty containers and lambdas need enough contextual type information.

## Statements, expressions, and operators

Allowed statements are declarations, assignments, expression statements,
`pass`, `return`, `assert`, `if`/`elif`/`else`, `match`/`case`, and function
definitions. Imports and type definitions have the module rules below.

Allowed expressions include variables, numbers, strings, Booleans, `None`,
lists, parenthesized tuples, string-keyed dictionaries, calls, supported
attribute access, indexing, conditional expressions, lambdas, list
comprehensions, and dictionary comprehensions. A comprehension generator has
a simple variable target, with optional Boolean filters. Iterate lists,
tuples, strings, dictionary keys, or the supported `range` type.

Supported binary operators are `+`, `-`, `*`, `/`, `//`, `%`, `**`,
`==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`, `and`, and `or`.
Unary operators are `+`, `-`, and `not`. Use only their supported overloads:
numeric arithmetic, numeric/string ordering, string/list/tuple concatenation,
string/list repetition, compatible structural equality, and supported membership.
Integer power with a nonnegative literal exponent returns `int`; other powers
may have a `float` result type. Follow Python precedence and short circuiting.

Conditions and filters, operands of `and`/`or`, and operands of `not` must be
`bool`. Write `len(xs) > 0`, not `if xs`. Assert messages must be strings.
Use parenthesized binary combinations for longer Boolean expressions and
comparisons: `(0 <= i) and (i < n)`, not `0 <= i < n`.

Index lists and strings with `int`, and dictionaries with `str`. Fixed tuple
indexing follows the component type for a known in-range literal index;
otherwise its type is the join of component types. Negative indices are allowed.
Slicing is excluded, including `xs[1:]` and `s[::-1]`. Attribute access is for
declared object fields and available module members; built-in value methods
such as `xs.append`, `xs.count`, `d.get`, and `s.lower` are unavailable.

Exclude `for`/`while` statements, `break`, `continue`, exceptions and handlers,
context managers, generators and generator expressions, `yield`, coroutines,
`async`/`await`, sets, f-strings, identity operators, bitwise operators,
matrix multiplication, starred expressions, and dictionary unpacking.
These boundaries describe this pinned core, including features marked as
planned or not yet supported; they do not assert those features are inherently
incompatible with every future PurePy version.

## Dataclasses, aliases, and patterns

Declare classes only at module level with exactly the bare `@dataclass`
decorator, imported from `dataclasses`. A body contains annotated fields without
default values, or `pass` for an empty class. Exclude methods, custom constructors,
other decorators, decorator options such as `frozen=True`, and multiple
inheritance. A single dataclass base is allowed; inherited fields cannot be
redeclared. Immutability is enforced by the PurePy language discipline.

Contiguous module-level dataclasses and `type` statements form a mutual type
region in v0.19.0. Forward type references follow the specification's region
resolution rules; recursive alias resolution and cyclic inheritance are
rejected. Do not infer executable Python annotation behavior merely from
checker acceptance; use CPython execution to validate an advanced construction.
Modules, class names, and aliases are not ordinary first-class data: class names
are used as types, constructors, or constructor patterns, and modules are used
to select available members.

Patterns may be literals, variables, `_`, bracketed list patterns,
parenthesized tuple patterns, constructor patterns, string-literal-keyed
dictionary patterns, and `p as x`. Exclude case guards, star/rest patterns,
or-patterns, and bare unparenthesized sequence patterns. A constructor pattern
covers all fields exactly once; `range` cannot be a constructor pattern.

List and tuple patterns must match their respective types. A pattern must not
rebind an already declared local name or bind the same variable twice. Cases
are checked in order and every case must be reachable. Pattern bindings obey
definite assignment after `match`; nonexhaustive matches may fall through.
Use a reachable catch-all where needed to establish returns, while respecting
the checker's type-based reachability and exhaustiveness analysis.

## Modules and predefined operations

All imports form a prefix before other module statements, including docstrings.
Use `import module` (one module per statement) or
`from module import name1, name2`. Exclude import aliases, relative imports,
wildcards, imports in functions, import cycles, and member/submodule name
collisions. Explicitly import submodules you reference; another module's
incidental loading does not establish availability. Imported names are private
dependencies rather than automatically re-exported members. Do not redeclare
the intrinsic `__name__` binding.

The predefined surface is limited to this table plus each module's `__name__`:

| Module | Available members and signatures |
| --- | --- |
| `builtins` | `print(object) -> None`; `len(Sized) -> int`; `range(start: int, stop: int)` as the predefined range constructor |
| `math` | `pi`, `e`: `float`; `sqrt`, `exp`, `log`, `sin`, `cos`, `tan`: `(float) -> float`; `floor`, `ceil`: `(float) -> int` |
| `sys` | `argv: list[str]`; `exit(int) -> Never` |
| `typing` | Annotation names `Callable`, `Literal`, `Never`, `Sized` |
| `dataclasses` | The decorator name `dataclass` |

The predefined range has `start` and `stop` fields and iterates integers from
start inclusive to stop exclusive, with unit positive step. Use `range(0, n)`
for indices. Neither `range(n)` nor `range(start, stop, step)` is accepted in
this version. `print` takes exactly one positional object; Python's additional
print arguments/options are not included.

Names such as `int`, `float`, `str`, `bool`, `list`, `dict`, `tuple`, and
`object` designate annotation forms, not general conversion constructors in
expressions. Do not call `int(x)`, `str(x)`, `list(xs)`, or `dict(...)`.
Other familiar Python functions/libraries, including `sum`, `min`, `max`,
`abs`, `sorted`, `enumerate`, `zip`, `map`, `filter`, `functools`, `collections`,
NumPy, and Pandas are not supplied by this predefined environment. Additional
user modules must themselves conform to the selected PurePy version.

## Dynamic boundaries and extensions

Equality uses compatible structural types. Function equality and Boolean versus
numeric equality are excluded. Hiding values behind `object` does not make
otherwise undefined comparisons legitimate. Comparing two NaNs within
container equality/membership is dynamically excluded when that comparison is
reached; direct `nan == nan` remains false. Earlier short circuiting can decide
the result without reaching an undefined comparison.

Index/key errors, failed assertions, division by zero, and nontermination remain
possible in a well-formed program. Keep checker acceptance and task test results
separate, and do not claim a formal proof from either.

Partial application by omitting arguments and piecewise pattern clauses in
function definitions belong to proposed extensions; neither is in this core.
Unchecked PurePy is an experimental condition with optional annotations and
without the well-formedness rules. Its separate prompt and syntax checker must
define that condition explicitly.
