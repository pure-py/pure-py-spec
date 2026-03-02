# PurePy - A Pure Functional Subset of Python

## [v0.1.3](https://github.com/pure-py/pure-py-spec/releases/download/v0.1.3/PurePy-spec.pdf)

PurePy defines a pure (side-effect free) subset of Python, intended initially for use by researchers in
programming languages and programming pedagogy, with a view to evolving it into a common language for scientific computing, supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The PurePy language standard will define a (versioned) formal grammar for the language, a formal semantics, and a reference interpreter.
All languages which are PurePy-compliant must accept any valid PurePy program and are
expected to behave in a way which conforms to, or at least coheres with, the formal semantics.

## Release workflow

Run the `Sync version numbers` GitHub Action manually with a version like `0.1.4`.
This updates version numbers on `main`, commits them, and then creates and pushes tag `v0.1.4`.
The tag push triggers the build workflow, which uploads `PurePy-spec.pdf` to the GitHub Release.

## Extensions

Implementations are allowed to have additional behaviours and syntax beyond the PurePy spec, as long as they maintain compatibility with the PurePy subset. For example, Python itself supports many additional features, like mutable variables and exceptions; Fluid has a matrix literal notation and allows functions to be defined by pattern-matching clauses.

## Existing implementations

Languages/language implementations we would like to be PurePy compliant:

- CPython
- JAX
- [Fluid](https://github.com/explorable-viz/fluid)
- fortl

Fluid will require some changes to be PurePy-compliant, especially with regard to lists, which in some ways look in some ways like Python lists, but behave quite differently. (There is no equivalent of "cons" in Python.)

## Long-term aims

The longer-term aim is to stimulate new language developments to support science. Centering around a common syntax
eases adoption and engagement with these new language techniques and ideas. In later version we may add support for type annotations, [Python array API](https://data-apis.org/array-api/latest/)-compatible arrays, and other features.

## Design concerns

One risk is that it is easy for users to get
confused about what is, and is not, valid PurePy syntax, e.g., writing Python code in another
PurePy-compliant language which does not accept non-PurePy Python features (such as exceptions). These points can be quite subtle, and could also cause problems in the other direction. For example, in Python one cannot efficiently construct a list by writing
```python
[x, *xs]
```
since `xs` is always copied. In a pure language with no assignment, this can be efficiently implemented by sharing `xs` into the new list. But encouraging users of PurePy to write list-manipulating code in this FP style might not be a good idea, since taking that style back to standard Python would result in non-idiomatic, unperformant code. Neverthless, we think a pure dialect of Python is a fruitful direction to explore, potentially enabling a flourishing of new language
ideas to benefit science in a way that reduces friction and barriers to entry.
