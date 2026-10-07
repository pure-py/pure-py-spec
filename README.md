# PurePy - A Pure Functional Subset of Python

[![build](https://github.com/pure-py/pure-py-spec/actions/workflows/build.yml/badge.svg)](https://github.com/pure-py/pure-py-spec/actions/workflows/build.yml)

## [v0.18.1](https://github.com/pure-py/pure-py-spec/releases/download/v0.18.1/PurePy-spec.pdf)

PurePy is a pure (side-effect free) subset of Python, intended initially for researchers in programming
languages and programming pedagogy, and in the longer term as a common language for scientific computing,
supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The specification defines a versioned formal grammar and a formal semantics for the language, and `src/`
holds a reference checker. A PurePy-compliant language accepts every valid PurePy program and is expected
to conform to the formal semantics.

## Project structure

- `paper.tex`: the paper
- `PurePy-spec.tex`: the language specification, a standalone document
- `spec/`: sources of the specification, from which the paper is also assembled
- `paper/`: material belonging only to the paper
- `tex/`: macros and bibliography shared by both documents
- `graduality.tex`, `graduality/`: draft notes on gradual typing, built as a separate document and not part of the 1.0 specification or paper
- `agda/`: Agda mechanisation of the distributivity proof
- `isabelle-purepy/`: Isabelle/HOL mechanisation, a submodule of the `isabelle-purepy` repository
- `src/`: reference checker, built on Python's `ast` and organised to mirror the sections of the specification
- `test/`: litmus tests

`\paperinput{file}` at a point in a specification source includes the file in the paper only, and
`\specinput{file}` in the specification only; `\paperonly{...}` and `\speconly{...}` restrict a phrase to
one document. Rules included individually in the paper are defined in `spec/rules/`, so that each rule has
one source; all other rules are defined in the figures.

## Building

See the Makefile.

## Tests

Install [uv](https://docs.astral.sh/uv/). The Python version in `.python-version` is read by uv, the
workflows, mypy and the specification; `pyproject.toml` gives only the lower bound. From the repository root:

```bash
uv run --locked ./test/run-all.sh
```

The command creates the project environment, installs the locked development dependencies and runs the suite,
which begins with mypy and ruff over `src/`.

Tests are organised by tier, `module-level/` and `program-level/`, then by verdict and stage; the runner
derives every assertion from the path. A module-level test is a `.py` file with expectation files as siblings
(`.expected`, `.error.expected`, `.exception.expected`, `.status.expected`); a program-level test is a
directory holding `main.py`, the expectation files of `main.py` and the other modules of the program.

- `semantically-valid/`: accepted by PurePy; runs under Python with the expected output and type-checks under mypy (`test/mypy.ini`)
- `excluded/`: accepted by Python but excluded by PurePy, in `syntactic/` at parse, in `static/` at check and in `dynamic/` at run time
- `python-error/`: rejected by both languages, with stages as above plus `syntactic-only/`, whose tests construct the form as an AST because Python source cannot express the form
- `semantically-valid/pending/`: not yet accepted by the checker

The runner requires an `excluded` test to run under Python and a `python-error` test to raise, so a test has
either `.expected` or `.exception.expected` and a misfiled test fails. A test that exits with a nonzero status
through `sys.exit` states the status in `.status.expected`.

Another checker can be run over the suite with `--checker`; `run-all.py --help` lists the options.

## Development

Synchronise the project environment and install the development dependencies:

```bash
uv sync --locked
```

Format the sources:

```bash
uv run --locked ruff format ./src ./test/run-all.py
```

After changing dependencies or metadata in `pyproject.toml`, run `uv lock` and commit `pyproject.toml` and
`uv.lock`.

## Reference checker (`src/`)

Check a single module, or a whole program from the entry module:

```bash
uv run --locked python src/check_module.py path/to/module.py
uv run --locked python src/check_program.py path/to/main.py
```

## PLDI 2027 submission

`make paper-submission` builds the anonymised paper and `supplementary.zip`, which carries the anonymised
specification and the Isabelle mechanisation. The target refuses to build unless the `isabelle-purepy`
submodule is checked out, has no uncommitted changes and sits at a commit on `origin/main`, so a submission
never ships a working copy. Check the submodule out with:

```bash
git submodule update --init
```

The mechanisation is type checked before packaging, so `isabelle` must be on `PATH`; the README of the
submodule gives the required version and installation steps. The `Build` GitHub Action runs `make all`, which
includes the submission target, on every push, but the submission is always built locally.

## Release workflow

Run the `Bump version` GitHub Action manually with a version in the form `x.y.z` (for example, `0.1.4`). The
action updates and commits the version numbers on `main`, creates and pushes the tag `v0.1.4`, then builds
`PurePy-spec.pdf` and attaches the PDF to the GitHub Release for the tag.

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
since `xs` is always copied. In a pure language with no assignment, this can be efficiently implemented by sharing `xs` into the new list. But encouraging users of PurePy to write list-manipulating code in this FP style might not be a good idea, since taking that style back to standard Python would result in non-idiomatic, unperformant code. Neverthless, we think a pure dialect of Python is a fruitful direction to explore, potentially enabling a flourishing of new language
ideas to benefit science in a way that reduces friction and barriers to entry.
