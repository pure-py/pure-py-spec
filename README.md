# PurePy - A Pure Functional Subset of Python

[![build](https://github.com/pure-py/pure-py-spec/actions/workflows/build.yml/badge.svg)](https://github.com/pure-py/pure-py-spec/actions/workflows/build.yml)

## [v0.23.0](https://pure-py.github.io/pure-py-spec/v0.23.0/PurePy-spec.pdf)

PurePy is a pure (side-effect free) subset of Python, intended initially for researchers in programming
languages and programming pedagogy, and in the longer term as a common language for scientific computing,
supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The specification defines a versioned formal grammar and a formal semantics for the language, and `src/purepy/`
holds the `purepy` reference type checker. A PurePy-compliant language accepts every valid PurePy program and is
expected to conform to the formal semantics.

## Project structure

- `paper.tex`: the paper
- `PurePy-spec.tex`: the language specification, a standalone document
- `spec/`: sources of the specification, from which the paper is also assembled
- `paper/`: material belonging only to the paper
- `tex/`: macros and bibliography shared by both documents
- `graduality.tex`, `graduality/`: draft notes on gradual typing, built as a separate document and not part of the 1.0 specification or paper
- `agda/`: Agda mechanisation of the distributivity proof
- `isabelle-purepy/`: Isabelle/HOL mechanisation, a submodule of the `isabelle-purepy` repository
- `src/purepy/`: the `purepy` reference type checker package, built on Python's `ast` and organised to mirror the sections of the specification
- `src/purepy/conformance-suite/`: the conformance suite, shipped in the package
- `test/`: runner for the conformance suite and checks of the repository

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

The command creates the project environment, installs the locked development dependencies, checks rule
cross-references, runs mypy and ruff over `src/purepy/` and runs the conformance suite.

Tests in `src/purepy/conformance-suite/` are organised by the outcome under Python and the outcome under
PurePy, following the grid in the conformance section of the specification; the runner derives every
assertion from the path. A test of one module is a `.py` file with expectation files as siblings
(`.expected`, `.error.expected`, `.exception.expected`, `.status.expected`); a test of a program of several
modules is a directory holding `main.py`, the expectation files of `main.py` and the other modules.

The outcome under Python is one of:

- `python-rejects/`: Python raises `SyntaxError` before running the program
- `python-raises/`: Python raises another exception while running the program
- `python-succeeds/`: Python runs the program with the expected output

The outcome under PurePy is one of:

- `parser-rejects/`: rejected by the parser
- `typing-rejects/`: rejected by the type checker
- `undefined/`: well-formed, and the run aborts with termination kind `undef`
- `agrees/`: well-formed, and the run yields the same result as under Python, including the same exception

The directory `python-succeeds/agrees/mypy-bug/` holds tests rejected by mypy because of a behaviour reported as a
mypy bug; the runner fails a test if mypy accepts it.

Every other test in `python-succeeds/agrees/` also type-checks under mypy (`test/mypy.ini`). The tests in
`syntactic-only/` construct a form as an AST, because Python source cannot express the form, and
check that PurePy rejects it.

A test has `.expected` under `python-succeeds/` and `.exception.expected` elsewhere, naming `SyntaxError` exactly
under `python-rejects/`, so a misfiled test fails. A test that exits with a nonzero status through `sys.exit`
states the status in `.status.expected`.

Every test under `typing-rejects/`, `undefined/` and `agrees/` names a rule of the specification on its first line,
as `# rule: name`. Under `typing-rejects/` the rule is the one with a premise or side condition that fails for the
program. Under `undefined/` and `agrees/` the rule is the one yielding the result.

Another type checker can be run over the suite installed with the `purepy` package, by passing a command
which takes the path of a test and exits with the codes of the reference type checker:

```bash
purepy-conformance --no-run --type-checker CMD --known-failures FILE
```

The run passes if its failures are exactly those listed in the file; `--update` rewrites the file, and
`purepy-conformance --help` lists the other options.

The type checker generated from the Isabelle mechanisation is such a type checker. `purepy-mechanised` parses
the program of an entry module with the reference parser, every module under the entry's directory up
front as the program of the specification, translates it into the mechanised syntax and checks it
with the generated code, which `make build` in `isabelle-purepy/` writes under `python/python_out/` and
which must be on `PYTHONPATH`. A program outside the mechanised fragment, such as one with a float literal
outside the reals, exits with code 5. The runner checks a test of one module as a program of that module
alone, away from its siblings. The failures of the suite under the generated type checker are listed in
`test/mechanised-failures.txt`, so the list measures the fragment; `make check-mechanised-type-checker` builds
the mechanisation and runs the suite against the list, as the Build workflow does.

## Development

Synchronise the project environment and install the development dependencies:

```bash
uv sync --locked
```

Format the sources:

```bash
uv run --locked ruff format ./src/purepy ./test/run-all.py
```

After changing dependencies or metadata in `pyproject.toml`, run `uv lock` and commit `pyproject.toml` and
`uv.lock`.

To build a distributable wheel and source archive:

```bash
uv build
```

## Reference type checker (`purepy`)

Check a single module, or a whole program from the entry module:

```bash
uv run --locked python -m purepy --check --module path/to/module.py
uv run --locked python -m purepy --check path/to/main.py
```

After installing the project as a standalone command-line tool, the same checks are available through the
`purepy` command:

```bash
purepy --check --module path/to/module.py
purepy --check path/to/main.py
```

Install the type checker from the repository root with:

```bash
uv tool install .
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
action updates and commits the version numbers on `main` and creates and pushes the tag `v0.1.4`. It then builds
`PurePy-spec.pdf` and publishes it to GitHub Pages under `v0.1.4/` and `latest/`
(https://pure-py.github.io/pure-py-spec/), and creates the GitHub Release for the tag, with the wheel and source
distribution of the `purepy` package attached.

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
