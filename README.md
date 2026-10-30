# PurePy - A Pure Functional Subset of Python

[![consistency checks](https://github.com/pure-py/pure-py-spec/actions/workflows/consistency-checks.yml/badge.svg)](https://github.com/pure-py/pure-py-spec/actions/workflows/consistency-checks.yml)

## [v0.23.2](https://pure-py.github.io/pure-py-spec/v0.23.2/PurePy-spec.pdf)

PurePy is a pure (side-effect free) subset of Python, intended initially for researchers in programming
languages and programming pedagogy, and in the longer term as a common language for scientific computing,
supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The specification defines a versioned formal grammar and a formal semantics for the language, and the
`purepy-conformance` package holds the conformance suite and its runner, which checks an implementation against
the suite. A PurePy-compliant language accepts every valid PurePy program and is expected to conform to the formal
semantics.

## Project structure

- `paper.tex`: the paper
- `PurePy-spec.tex`: the language specification, a standalone document
- `spec/`: sources of the specification, including the figures, rules, definitions and lemmas shared with the paper
- `paper/`: sources of the paper's own prose, and in `paper/fig/` key figures laid out for the paper
- `tex/`: macros and bibliography shared by both documents
- `graduality.tex`, `graduality/`: draft notes on gradual typing, built as a separate document and not part of the 1.0 specification or paper
- `src/purepy_conformance/`: the conformance suite, as package data, and its runner, the `purepy-conformance` command
- `test/`: consistency of the specification with the conformance suite, and of the suite with mypy
- `script/`: project board integrity check, run daily by CI

Each section has separate prose in the two documents, `paper/<section>.tex` and `spec/<section>.tex`, and
the technical material has one source: figures in `spec/fig/`, apart from key figures such as the syntax of
statements, which the paper lays out differently in `paper/fig/`; rules included individually in the paper in
`spec/rules/`, and definitions and lemmas in `spec/<section>/`, input by both documents. Within a shared
source, `\paperonly{...}` and `\speconly{...}` restrict a phrase to one document. The syntax and operational
semantics sections are still assembled from one source each, in which `\paperinput{file}` includes a file in
the paper only and `\specinput{file}` in the specification only.

## Building

See the Makefile.

## Conformance suite

Install [uv](https://docs.astral.sh/uv/). The Python version in `.python-version` is read by uv, the
workflows, mypy and the specification. From the repository root, check that every test cites a rule of the
specification, run the suite against Python with mypy as type checker, and build the wheel:

```bash
make wheel
```

An implementation runs the suite with the `purepy-conformance` command of the installed package, giving the
command which type-checks the module at the path appended to it and, optionally, the Python interpreter which
runs the tests:

```bash
purepy-conformance --type-checker "purepy --check" python3
```

## Development

Synchronise the project environment and install the development dependencies:

```bash
uv sync --locked
```

Format the script:

```bash
uv run --locked ruff format ./test/consistency.py ./src/purepy_conformance
```

## PLDI 2027 submission

`make paper-submission` builds the anonymised paper and `supplementary.zip`, which carries the anonymised
specification and the Isabelle mechanisation, cloned from the `isabelle-purepy` repository at the `purepy`
release of the same version, which is the release checked against this specification. The archive is not checked after anonymisation (#292).

The submission is always built locally; the `Consistency checks` GitHub Action runs the consistency script,
the `Paper` action builds the paper and specification and runs the evaluation pipeline, and the mechanisation and
type checker are checked by the `build` action of their repository.

## Release workflow

Run the `Bump version` GitHub Action manually with a version in the form `x.y.z`.

### Zotero export settings

Bibliography management uses the [PurePy Zotero library](https://www.zotero.org/groups/6458996/purepy/library).
Install the Better BibTeX plugin with the following changes to the default settings, which avoid spurious diffs:

- Citation key formula: auth.lower + year
- Fields to omit from export: abstract, keywords

Export the library to `tex/zotero-export.bib`. A reference not yet in the library goes in
`tex/additional-refs.bib` by hand until imported.

## Design concerns

One risk is that it is easy for users to get
confused about what is, and is not, valid PurePy syntax, e.g., writing Python code in another
PurePy-compliant language which does not accept non-PurePy Python features (such as exceptions). These points can be quite subtle, and could also cause problems in the other direction. For example, in Python one cannot efficiently construct a list by writing
```python
[x, *xs]
```
since `xs` is always copied. In a pure language with no assignment, this can be efficiently implemented by sharing `xs` into the new list. But encouraging users of PurePy to write list-manipulating code in this FP style might not be a good idea, since taking that style back to standard Python would result in non-idiomatic, unperformant code. Nevertheless, we think a pure dialect of Python is a fruitful direction to explore, potentially enabling a flourishing of new language
ideas to benefit science in a way that reduces friction and barriers to entry.
