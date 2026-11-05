# OurLang formalisation in Isabelle/HOL


This repository holds the Isabelle/HOL mechanisation of the OurLang specification and the `ourlang` type checker
generated from the mechanisation.

## Building

Install the [Isabelle](https://isabelle.in.tum.de/) release named in `.isabelle-version` and
[uv](https://docs.astral.sh/uv/). Then check the proofs and generate the type checker:

```bash
make build
```

To browse the theories with the prover running, open the session directory in the bundled editor:

```bash
./vscode.sh
```

## Type checker (`ourlang`)

The `ourlang` package in `src/ourlang/` contains the generated type checker and the code which runs it on source
files.

Install the wheel attached to the latest [release](https://github.com/ourlang/mechanisation/releases) as a
standalone command-line tool with `uv tool install <wheel URL>`. Then check a single module, or a whole program
from the entry module:

```bash
ourlang --check --module path/to/module.py
ourlang --check path/to/main.py
```

From a checkout, after `make build`, the same checks run with `uv run --locked python -m ourlang --check`.

## Tests

After `make build`:

```bash
make check-conformance
```

The conformance suite comes from the pinned specification.

## Development

Synchronise the project environment and install the development dependencies:

```bash
uv sync --locked
```

Format the sources:

```bash
uv run --locked ruff format ./src/ourlang ./test/check-conformance.py
```

After changing dependencies or metadata in `pyproject.toml`, run `uv lock` and commit `pyproject.toml` and
`uv.lock`.

## Release workflow

Run the `Release` GitHub Action manually. The version number of a release is that of the pinned
`ourlang-conformance` release.

## Theories

<!-- theories -->
| File                 | Content                                                                        |
|----------------------|--------------------------------------------------------------------------------|
| `Util.thy`           | Shared utilities                                                               |
| `Floats.thy`         | Floats as an abstract type with uninterpreted arithmetic                       |
| `Strings.thy`        | Strings and identifiers as lists of Unicode code points                        |
| `Positions.thy`      | Syntax nodes with their positions in the source                                |
| `Syntax.thy`         | Abstract syntax and syntactic analyses                                         |
| `Semantics.thy`      | Values, results and evaluation judgements                                      |
| `Correctness.thy`    | Inversion lemmas and determinism of evaluation                                 |
| `Contexts.thy`       | Context entries, class tables, name resolution, predefined modules             |
| `Reasons.thy`        | Reasons for ill-formedness                                                     |
| `Types.thy`          | Type resolution, substitution and class definitions                            |
| `Subtyping.thy`      | Subtyping, join and meet; element, subscript and attribute types               |
| `Shapes.thy`         | Heads and shapes for pattern matching; head and shape typing; shapes of a type |
| `Patterns.thy`       | Pattern checking; matched and remaining types of patterns                      |
| `Matching.thy`       | Splitting of shapes; matching of patterns against shapes                       |
| `Operators.thy`      | Equality types and operator overloads                                          |
| `Typing.thy`         | Static outcomes; typing of expressions, statements and type definitions        |
| `Programs.thy`       | Typing of imports, modules and programs                                        |
| `Examples.thy`       | Example evaluations                                                            |
| `python/Codegen.thy` | Operator resolution and subtyping in executable form; Python generation        |
<!-- /theories -->
