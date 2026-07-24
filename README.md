# PurePy - A Pure Functional Subset of Python

## [v0.11.1](https://github.com/pure-py/pure-py-spec/releases/download/v0.11.1/PurePy-spec.pdf)

PurePy defines a pure (side-effect free) subset of Python, intended initially for use by researchers in
programming languages and programming pedagogy, with a view to evolving it into a common language for scientific computing, supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The PurePy language standard will define a (versioned) formal grammar for the language, a formal semantics, and a reference interpreter.
All languages which are PurePy-compliant must accept any valid PurePy program and are
expected to behave in a way which conforms to, or at least coheres with, the formal semantics.

## Project structure

- `PurePy-spec.tex` — main spec document
- `tex/` — macros, listings config, related work
- `fig/` — syntax, well-formedness rules, operational semantics
- `agda/` — Agda mechanisation (distributivity proof)
- `src/` — reference checker (Python `ast`-based), organised to mirror the spec's sections
- `test/` — litmus tests

## Building the spec

```
latexmk -pdf PurePy-spec.tex
```

## Running tests

```
test/run-all.sh
```

Sets up a `.venv` automatically. Targets Python 3.12+ ([#39](https://github.com/pure-py/pure-py-spec/issues/39)).

Tests are organised by tier (per-module $\Gamma \vdash_M m : \Delta$ and program-level $\vdash \langle E, \mathcal{M} \rangle$) and then by verdict. The verdict directory *is* the test's specification: the runner derives every assertion from the path.
- `well-formed/` — PurePy accepts; Python runs it
- `prohibited/` — PurePy rejects but Python accepts (valid Python excluded by design); `syntactic/` is rejected at parse, `semantic/` at check
- `ill-formed/` — PurePy rejects *and* Python rejects (a genuine error); `semantic/` carries the Python exception, `syntactic-only/` is tested via AST construction (not expressible as `.py`)
- `pending/` — not yet implemented; will become well-formed

The invariant — `prohibited` ⇒ Python runs it, `ill-formed` ⇒ Python rejects it — is enforced by the runner (a test must carry `.expected` xor `.exception.expected`), so a misfiled test fails.

## Reference checker (`src/`)

`parse.py` decides whether a Python program belongs to the PurePy subset, using the `ast` module;
`check_module.py` and `check_program.py` check well-formedness at module and program level.

- Exit 0: accepted
- Exit 1: prohibited (permanently excluded)
- Exit 2: not yet supported (planned, linked to a GitHub issue)

## Release workflow

Run the `Bump version` GitHub Action manually with a version in the form `x.y.z` (for example, `0.1.4`).
This updates version numbers on `main`, commits them, creates and pushes tag `v0.1.4`, then builds `PurePy-spec.pdf` and uploads it to the GitHub Release for that tag.

### Zotero export settings

Use the [PurePy Zotero library](https://www.zotero.org/groups/6458996/purepy/library) for bibliography
management. Install the Better BibTeX plugin, with the following modifications to the default settings to
avoid spurious diffs:
- Citation key formula: auth.lower + year
- Fields to omit from export: abstract, keywords

## Extensions

Implementations are allowed to have additional behaviours and syntax beyond the PurePy spec, as long as they maintain compatibility with the PurePy subset. For example, Python itself supports many additional features, like mutable variables and exceptions; Fluid has a matrix literal notation and allows functions to be defined by pattern-matching clauses.

## Existing implementations

Languages/language implementations we would like to be PurePy compliant:

- Python
- JAX
- [Fluid](https://github.com/explorable-viz/fluid)
- fortl

Fluid will require some changes to be PurePy-compliant, especially with regard to lists, which in some ways look in some ways like Python lists, but behave quite differently. (There is no equivalent of "cons" in Python.)

## Long-term aims

The longer-term aim is to stimulate new language developments to support science. Centering around a common syntax
eases adoption and engagement with these new language techniques and ideas. In later version we may add support for type annotations, [Python array API](https://data-apis.org/array-api/latest/)-compatible arrays, and other features.

## GitHub CLI (`gh`) setup

When working across multiple GitHub organisations, set `GH_TOKEN` per terminal session to avoid keyring conflicts:

```bash
export GH_TOKEN=<your-pure-py-pat>
```

For Claude Code, this can be configured automatically via `.claude/settings.local.json` (gitignored):

```json
{"env": {"GH_TOKEN": "<your-pure-py-pat>"}}
```

## Design concerns

One risk is that it is easy for users to get
confused about what is, and is not, valid PurePy syntax, e.g., writing Python code in another
PurePy-compliant language which does not accept non-PurePy Python features (such as exceptions). These points can be quite subtle, and could also cause problems in the other direction. For example, in Python one cannot efficiently construct a list by writing
```python
[x, *xs]
```
since `xs` is always copied. In a pure language with no assignment, this can be efficiently implemented by sharing `xs` into the new list. But encouraging users of PurePy to write list-manipulating code in this FP style might not be a good idea, since taking that style back to standard Python would result in non-idiomatic, unperformant code. Neverthless, we think a pure dialect of Python is a fruitful direction to explore, potentially enabling a flourishing of new language
ideas to benefit science in a way that reduces friction and barriers to entry.
