# PurePy - A Pure Functional Subset of Python

[![status page](https://github.com/pure-py/org-workflow/actions/workflows/status.yml/badge.svg)](https://pure-py.github.io/org-workflow/status.html)

## [v0.27.5](https://pure-py.github.io/pure-py-spec/v0.27.5/PurePy-spec.pdf)

PurePy is a pure (side-effect free) subset of Python, intended initially for researchers in programming
languages, and in the longer term as a common language for scientific computing,
supporting efficient, portable applications in modelling, data processing, data analysis and visualisation.

The specification defines a versioned formal grammar and a formal semantics for the language, and the
`purepy-conformance` package holds the conformance suite and its runner, which checks an implementation against
the suite. A PurePy-compliant language accepts every valid PurePy program and is expected to conform to the formal
semantics.

## Building

`make help` lists the targets. Enable the git hooks once per clone:

```bash
git config core.hooksPath script/hooks
```

## Conformance suite

An implementation runs the suite with the `purepy-conformance` command, providing a type checker and interpreter
(default `python3`), each as a command taking the path of a module:

```bash
purepy-conformance --type-checker "purepy --check" purepy
```

The type checker rejects a program by exit status 5 if it uses a feature excluded from this version, and otherwise
by 1 if outside the syntax of PurePy and 3 if ill-formed. An interpreter which prints `purepy` when given the
option `--implementation` is a PurePy implementation; it must report undefined behaviour by exit status 4 on the tests
under `undefined`, and give the recorded Python outcome on every other test. Any other interpreter must be a Python
implementation, and give the recorded Python outcome on every test.

## Release workflow

Run the `Bump version` GitHub Action manually with a version in the form `x.y.z`.

### Zotero export settings

Bibliography management uses the [PurePy Zotero library](https://www.zotero.org/groups/6458996/purepy/library).
Install the Better BibTeX plugin with the following changes to the default settings, which avoid spurious diffs:

- Citation key formula: auth.lower + year
- Fields to omit from export: abstract, keywords

Export the library to `tex/zotero-export.bib`. A reference not yet in the library goes in
`tex/additional-refs.bib` by hand until imported.
