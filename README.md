PurePy - A Pure Functional Subset of Python
----------
PurePy defines a pure (side-effect free) subset of Python, intended initially for use by researchers in 
programming languages and programming pedagogy, with a view to evolving it into a common language for scientific computing, supporting efficient, portable applications inmodelling, data processing, data analysis and visualisation. 

The PurePy language standard will define a (versioned) formal grammar
for the language, a formal semantics, and a reference interpreter.

All languages which are PurePy-compliant must accept any valid PurePy program and are
expected to behave in a way which conforms to, or at least coheres with, the formal semantics.
Such languages are allowed to have additional behaviours and syntax beyond the PurePy spec, as long as they maintain compatibility with the PurePy subset.

Languages/language implementations which are currently PurePy-1.0.0 compliant:

- CPython
- JAX
- [Fluid](https://github.com/explorable-viz/fluid)
- fortl

The longer-term aim is to stimulate new language developments to support science. Centering around a common syntax
eases adoption and engagement with these new language techniques and ideas. In later version we may add support for type annotations, [Python array API](https://data-apis.org/array-api/latest/)-compatible arrays, and other features. 

One risk is that it is easy for users to get
confused about what is, and is not, valid PurePy syntax, e.g., writing Python code in another
PurePy-compliant language which does not accept non-PurePy Python features (such as exceptions).
We think this cost is worth the benefits, enabling a flourishing of new language
ideas to benefit science in a way that reduces friction and barriers to entry.
