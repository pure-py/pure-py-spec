# PurePy - A Pure Functional Subset of Python

[![build](https://github.com/pure-py/pure-py-spec/actions/workflows/build.yml/badge.svg)](https://github.com/pure-py/pure-py-spec/actions/workflows/build.yml)

## [v0.15.1](https://github.com/pure-py/pure-py-spec/releases/download/v0.15.1/PurePy-spec.pdf)

PurePy defines a pure (side-effect free) subset of Python, intended initially for use by researchers in
programming languages and programming pedagogy, with a view to evolving it into a common language for scientific computing, supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The PurePy language standard will define a (versioned) formal grammar for the language, a formal semantics, and a reference interpreter.
All languages which are PurePy-compliant must accept any valid PurePy program and are
expected to behave in a way which conforms to, or at least coheres with, the formal semantics.

## Project structure

- `paper.tex` — the paper
- `PurePy-spec.tex` — the language specification as a standalone document, separate from the paper (#134)
- `spec/` — the specification's sources; the paper is assembled from these
- `paper/` — material that belongs only to the paper
- `tex/` — macros and bibliography shared by both documents
- `graduality.tex`, `graduality/` — draft notes on gradual typing, built as a separate document and not part of the 1.0 specification or paper
- `agda/` — Agda mechanisation (distributivity proof), likely to migrate to Isabelle
- `isabelle-purepy/` — Isabelle/HOL mechanisation, a submodule of the `isabelle-purepy` repository
- `src/` — reference checker (Python `ast`-based), organised to mirror the spec's sections
- `test/` — litmus tests

The specification is the source of truth; the paper is built from its sections and definitions.
Material that belongs only to the paper is kept under `paper/`. To insert such material into a shared
section, write `\paperinput{file}` in the specification source where the material should go. The paper
includes the file at that point; the specification does not. `\specinput{file}` is the reverse: the
specification includes the file and the paper does not. `\paperonly{...}` and `\speconly{...}` do the
same for a phrase. The subfolders of `spec/` are self-explanatory, except that `spec/rules/` holds any
rules the paper needs to include on an individual basis, so that each has one source; all other rules
live in their figures.

## Building

See the Makefile.

## Running tests

Install [uv](https://docs.astral.sh/uv/). The Python version is the one in `.python-version`, which uv,
the workflows, mypy and the specification all read; `pyproject.toml` gives only the lower bound
([#39](https://github.com/pure-py/pure-py-spec/issues/39)).

From the repository root, run:

```bash
uv run --locked ./test/run-all.sh
```

This command creates the project environment, installs the locked development
dependencies, and runs the test suite.

## Development

Synchronize the project environment and install the development dependencies:

```bash
uv sync --locked
```

Apply Ruff formatting:

```bash
uv run --locked ruff format ./src ./test/run-all.py
```

When changing project dependencies or metadata, run:

```bash
uv lock
```

Review and commit the resulting changes to:

```text
pyproject.toml
uv.lock
```

Tests are organised by tier (module-level and program-level) and then by verdict. The verdict directory *is* the test's specification: the runner derives every assertion from the path.
- `semantically-valid/` — PurePy accepts; Python runs it and gives the same result
- `excluded/` — Python accepts but PurePy excludes by design; `syntactic/` is rejected at parse, `static/` at check, `dynamic/` at run time
- `python-error/` — neither language gives a result (a genuine error); stages as above, plus `syntactic-only/`, tested via AST construction (not expressible as `.py`)
- `pending/` — not yet decided by the checker; `semantically-valid/pending/` will become semantically valid, `<verdict>/static/pending/` will be rejected at check
- `semantically-valid/mypy-incompatible/` — PurePy accepts, mypy rejects; every other semantically-valid test must type-check under mypy (`test/mypy.ini`)

The invariant — `excluded` ⇒ Python runs it, `python-error` ⇒ Python raises — is enforced by the runner (a test must carry `.expected` xor `.exception.expected`), so a misfiled test fails.

## Reference checker (`src/`)

Check a single module, or a whole program from its entry module:

```bash
uv run --locked python src/check_module.py path/to/module.py
uv run --locked python src/check_program.py path/to/main.py
```

## PLDI 2027 submission

`make paper-submission` builds the anonymised paper and `supplementary.zip`, which carries the anonymised
specification and the Isabelle mechanisation. It refuses to build unless the `isabelle-purepy` submodule is
checked out, has no uncommitted changes, and sits at a commit that is on `origin/main`, so a
submission never ships a working copy. Check it out with:

```bash
git submodule update --init
```

The mechanisation is type checked before packaging, so `isabelle` must be on `PATH`; the submodule's
README gives the required version and installation steps. The `Build` GitHub Action runs `make all`,
which includes this target, on every push to validate the build, but the submission is always built
locally.

## Release workflow

Run the `Bump version` GitHub Action manually with a version in the form `x.y.z` (for example, `0.1.4`).
This updates version numbers on `main`, commits them, creates and pushes tag `v0.1.4`, then builds `PurePy-spec.pdf` and uploads it to the GitHub Release for that tag.

### Zotero export settings

Use the [PurePy Zotero library](https://www.zotero.org/groups/6458996/purepy/library) for bibliography
management. Install the Better BibTeX plugin, with the following modifications to the default settings to
avoid spurious diffs:
- Citation key formula: auth.lower + year
- Fields to omit from export: abstract, keywords

Export the library to `tex/zotero-export.bib`. A reference not yet in the library goes in
`tex/additional-refs.bib` by hand until it is imported.

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

## Design concerns

One risk is that it is easy for users to get
confused about what is, and is not, valid PurePy syntax, e.g., writing Python code in another
PurePy-compliant language which does not accept non-PurePy Python features (such as exceptions). These points can be quite subtle, and could also cause problems in the other direction. For example, in Python one cannot efficiently construct a list by writing
```python
[x, *xs]
```
since `xs` is always copied. In a pure language with no assignment, this can be efficiently implemented by sharing `xs` into the new list. But encouraging users of PurePy to write list-manipulating code in this FP style might not be a good idea, since taking that style back to standard Python would result in non-idiomatic, unperformant code. Neverthless, we think a pure dialect of Python is a fruitful direction to explore, potentially enabling a flourishing of new language
ideas to benefit science in a way that reduces friction and barriers to entry.
