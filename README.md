# PurePy - A Pure Functional Subset of Python

[![status page](https://github.com/pure-py/org-workflow/actions/workflows/status.yml/badge.svg)](https://pure-py.github.io/org-workflow/status.html)

## [v0.24.3](https://pure-py.github.io/pure-py-spec/v0.24.3/PurePy-spec.pdf)

PurePy is a pure (side-effect free) subset of Python, intended initially for researchers in programming
languages and programming pedagogy, and in the longer term as a common language for scientific computing,
supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The specification defines a versioned formal grammar and a formal semantics for the language, and the
`purepy-conformance` package holds the conformance suite and its runner, which checks an implementation against
the suite. A PurePy-compliant language accepts every valid PurePy program and is expected to conform to the formal
semantics.

## Project structure

- `paper.tex`: paper
- `PurePy-spec.tex`: language specification
- `spec/`: specification sources, including figures, rules, definitions and lemmas shared with paper
- `paper/`: paper prose not shared with specification
- `tex/`: macros and bibliography shared by both documents
- `graduality.tex`, `graduality/`: draft notes on gradual typing, built as a separate document, outside 1.0 specification and paper
- `src/purepy_conformance/`: conformance suite and its runner, `purepy-conformance` command, packaged together
- `test/`: consistency of specification and suite; expected failures of latest mechanisation release
- `script/`: scripts for the Makefile and CI

Each section has separate prose in the two documents, and material shared by both lives under `spec/` and is
input by each. Within a shared source, `\paperonly{...}` and `\speconly{...}` restrict a phrase to one document.

## Building

See the Makefile.

## Conformance suite

Install [uv](https://docs.astral.sh/uv/). The Python version in `.python-version` is read by uv, the
workflows, mypy and the specification. From the repository root, check that every test cites a rule of the
specification, run the suite against Python with mypy as type checker, and build the wheel:

```bash
make wheel
```

The reference implementation is the latest release of the mechanisation in the `isabelle-purepy` repository;
`make check-suite-purepy` runs the suite against it.

An implementation runs the suite with the `purepy-conformance` command of the installed package, providing a type
checker and interpreter (default `python3`), each as a command taking the path of a module. The type checker
checks every test, and rejects a program by exit status 5 if the program uses a feature excluded from this version,
and otherwise by 1 if outside the syntax of PurePy and 3 if ill-formed. The interpreter runs every well-formed test and must give the recorded Python outcome; reporting
undefined behaviour, by exit status 4, is also accepted when the run has undefined behaviour in PurePy.

```bash
purepy-conformance --type-checker "purepy --check" purepy
```

The files beside a test give its expectations: `.expected` holds the output of a test that succeeds, `.status.expected`
its exit status when non-zero, `.exception.expected` the exception raised by a test that raises, `.output.expected`
the output before the exception, `.error.expected` the diagnostic of the reference type checker for a test it
rejects, and `.args` the command-line arguments of a run, one per line.

An implementation conforms by its exit statuses, and may word diagnostics as it chooses. With `--check-messages`,
the suite also checks each diagnostic against `.error.expected`. The reference type checker is tested with this
option. A diagnostic for an excluded Python feature names the feature and says whether it is excluded by design or
from this version; its `.error.expected` ends with the placeholder `{classification}`, which the suite replaces by the
wording defined by `Classification` in the `purepy_conformance` package.

## Development

Synchronise the project environment and install the development dependencies:

```bash
uv sync --locked
```

Format the scripts:

```bash
uv run --locked ruff format ./test ./src/purepy_conformance
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
