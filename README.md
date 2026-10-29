# PurePy - A Pure Functional Subset of Python

[![consistency checks](https://github.com/pure-py/pure-py-spec/actions/workflows/consistency-checks.yml/badge.svg)](https://github.com/pure-py/pure-py-spec/actions/workflows/consistency-checks.yml)

## [v0.23.0](https://pure-py.github.io/pure-py-spec/v0.23.0/PurePy-spec.pdf)

PurePy is a pure (side-effect free) subset of Python, intended initially for researchers in programming
languages and programming pedagogy, and in the longer term as a common language for scientific computing,
supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The specification defines a versioned formal grammar and a formal semantics for the language. The `purepy` type
checker is generated from the Isabelle mechanisation in the
[isabelle-purepy](https://github.com/pure-py/isabelle-purepy) repository, which also holds the conformance suite.
A PurePy-compliant language accepts every valid PurePy program and is expected to conform to the formal
semantics.

## Project structure

- `paper.tex`: the paper
- `PurePy-spec.tex`: the language specification, a standalone document
- `spec/`: sources of the specification, from which the paper is also assembled
- `paper/`: material belonging only to the paper
- `tex/`: macros and bibliography shared by both documents
- `graduality.tex`, `graduality/`: draft notes on gradual typing, built as a separate document and not part of the 1.0 specification or paper
- `agda/`: Agda mechanisation of the distributivity proof
- `test/`: consistency of the specification with the conformance suite of the `purepy` release in `uv.lock`

`\paperinput{file}` at a point in a specification source includes the file in the paper only, and
`\specinput{file}` in the specification only; `\paperonly{...}` and `\speconly{...}` restrict a phrase to
one document. Rules included individually in the paper are defined in `spec/rules/`, so that each rule has
one source; all other rules are defined in the figures.

## Building

See the Makefile.

## Consistency checks

Install [uv](https://docs.astral.sh/uv/). The Python version in `.python-version` is read by uv, the
workflows, mypy and the specification; `pyproject.toml` gives only the lower bound. From the repository root:

```bash
make check-consistency
```

## Development

Synchronise the project environment and install the development dependencies:

```bash
uv sync --locked
```

Format the script:

```bash
uv run --locked ruff format ./test/consistency.py
```

To take a new `purepy` release, change the wheel URL in `pyproject.toml`, run `uv lock` and commit
`pyproject.toml` and `uv.lock`.

## PLDI 2027 submission

`make paper-submission` builds the anonymised paper and `supplementary.zip`, which carries the anonymised
specification and the Isabelle mechanisation, cloned from the `isabelle-purepy` repository at the `purepy`
release named in `pyproject.toml`. The archive is not checked after anonymisation (#292).

The submission is always built locally; the `Consistency checks` GitHub Action runs the consistency script,
the `Documents` action builds the paper and specification, and the mechanisation and
type checker are checked by the `build` action of their repository.

## Release workflow

Run the `Bump version` GitHub Action manually with a version in the form `x.y.z` (for example, `0.1.4`). The
action updates and commits the version numbers on `main` and creates and pushes the tag `v0.1.4`. It then builds
`PurePy-spec.pdf` and publishes it to GitHub Pages under `v0.1.4/` and `latest/`
(https://pure-py.github.io/pure-py-spec/), and creates the GitHub Release for the tag. The `purepy` package is
released from the `isabelle-purepy` repository.

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
