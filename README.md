UNISC - The Unified Syntax for Computational Science
----------
UNISC is a unified, common syntax for a exploratory research in a new wave of
programming languages, targetted specifically at computational science (scientific computing)
applications, e.g., modelling, data processing, data analysis, and visualisation. 

UNISC is heavily inspired by Python, which is popular across the sciences; it can be seen as
a pure (i.e., mutation free) subset of Python. The UNISC language standard defines a (versioned) formal grammar
for the language, a formal semantics, and a reference interpreter.

All languages which are UNISC-compliant must accept any valid UNISC program and are
expected to behave in a way which conforms, or at least coheres, with the reference
interpreter. Such languages are allowed to have behaviours and syntax that goes beyond UNISC,
i.e., they are supersets of UNISC.

Languages/language implementations which are currently UNISC-1.0.0 compliant:

- CPython
- JAX
- Fluid
- fortl
- Hazel

The aim is to stimulate new language developments to support science. Centering around a common syntax
eases adoption and engagement with these new language techniques and ideas.

One risk is that it is easy for users to get
confused about what is, and is not, valid UNISC syntax, e.g., writing Python code into another
UNISC-compliant language but which does not accept those particular non-UNISC Python features.
We think this cost is worth the benefits, enabling a flourishing of new language
ideas to benefit science in a way that reduces friction and barriers to entry.

